import json
import os
import threading

from base.auditory import AuditoryContext
from tools.log import logger
from tools.nls import NlsSpeechTranscriber
from tools.nls.token import getToken
from tools.redis_client import RedisClientProxy
from tools.time_fmt import get_timestamp

accessKeyId = os.getenv("ALI_ACCESS_KEY_ID")
accessKeySecret = os.getenv("ALI_ACCESS_KEY_SECRET")
appKey = os.getenv("ALI_APP_KEY")


class AliRealTimeASR(NlsSpeechTranscriber):
    def __init__(
            self,
            uid,
            accessKeyId=accessKeyId,
            accessKeySecret=accessKeySecret,
            appKey=appKey,
    ):
        self.__accessKeyId = accessKeyId
        self.__accessKeySecret = accessKeySecret
        self.__appKey = appKey
        self.__id = uid
        super().__init__(
            appkey=self.__appKey,
            token=getToken(self.__accessKeyId, self.__accessKeySecret),
            on_sentence_begin=self.on_sentence_begin,
            on_sentence_end=self.on_sentence_end,
            on_start=self.on_start,
            on_result_changed=self.on_result_changed,
            on_completed=self.on_completed,
            on_error=self.on_error,
            on_close=self.on_close,
            callback_args=[self.__id],
        )

        self.status = False
        self.lock = threading.Lock()
        self.start_time = get_timestamp()
        self.max_sentence_silence = 1500

    def set_status(self, status):
        with self.lock:
            self.status = status

    def get_status(self):
        with self.lock:
            return self.status

    def on_sentence_begin(self, message, *args):
        logger.info("on_sentence_begin:{} {}".format(message, *args))
        self.start_time = get_timestamp()

    def on_sentence_end(self, message, *args):
        logger.info("on_sentence_end:{} {}".format(message, *args))
        voice = AuditoryContext(
            current_time=get_timestamp(),
            user_id=self.__id,
            user_text=json.loads(message)["payload"]["result"],
        )
        RedisClientProxy.push_text_data(json.dumps(voice.dict()))
        asr_delay = voice.current_time - self.start_time + self.max_sentence_silence
        RedisClientProxy.set_user_statistic(voice.user_id, "asr_delay", asr_delay)
        logger.info("text for {}: {}".format(voice.user_id, voice.user_text))

    @staticmethod
    def on_start(message, *args):
        logger.info("on_start:{} {}".format(message, *args))

    def on_error(self, message, *args):
        logger.info("on_error:{} {}".format(message, *args))
        if self.get_status():
            self.set_status(False)
            logger.info("ali asr on_error closed")

    def on_close(self, *args):
        logger.info("on_close:{}".format(*args))
        if self.get_status():
            self.set_status(False)
            logger.info("ali asr on_close closed")

    def on_result_changed(self, message, *args):
        self.start_time = get_timestamp()
        logger.info("on_result_changed:{} {}".format(message, *args))

    def on_completed(self, message, *args):
        logger.info("on_completed:{} {}".format(message, *args))
        # if self.get_status():
        #     self.set_status(False)
        #     logger.info("ali asr completed")

    def push_audio(self, data, *args):
        try:
            if not self.get_status():
                self.start(
                    enable_intermediate_result=True,
                    enable_punctuation_prediction=True,
                    enable_inverse_text_normalization=True,
                    timeout=30,
                    ex={
                        "max_sentence_silence": self.max_sentence_silence,
                        # "enable_semantic_sentence_detection": True,
                    },
                )
                self.set_status(True)
                logger.info("ali asr start: {}".format(*args))
        except Exception as e:
            logger.error("ali asr start error:{}, {}".format(e, *args))
            self.set_status(False)
            raise Exception("ali asr start error:{}, {}".format(e, *args))

        try:
            self._NlsSpeechTranscriber__nls_token = getToken(
                self.__accessKeyId, self.__accessKeySecret
            )
        except Exception as e:
            logger.error("ali asr token error:{}, {}".format(e, *args))
            self.set_status(False)
            raise Exception("ali asr token error:{}, {}".format(e, *args))

        try:
            self.send_audio(data)
        except Exception as e:
            self.set_status(False)
            logger.error("ali asr error:{}, {}".format(e, *args))
            raise Exception("ali asr error:{}, {}".format(e, *args))
