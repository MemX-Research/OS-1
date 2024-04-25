import json
import time
import traceback
from multiprocessing import Queue
from threading import Thread

from base.auditory import AuditoryContext
from base.parser import DataParser
from tools.asr_api import RealTimeWhisperWithSilenceDetection
from tools.bs64 import bytes2bs64
from tools.helper import VoiceHelper, TextHelper
from tools.log import logger
from tools.redis_client import RedisClientProxy


class AudioWorker:
    @staticmethod
    def pull_audio(user_id):
        data = RedisClientProxy.pop_audio_data(user_id)
        if data is None:
            # RedisClientProxy.del_user(user_id)
            return None
        return json.loads(data)

    def process(self, user_id):
        data = self.pull_audio(user_id)
        if data is None:
            return

        audio_data = DataParser.parse_voice(data)
        if audio_data is None:
            return

        if VoiceHelper.is_silent(audio_data):
            return

        current_time = DataParser.parse_time(data)
        text, full_audio = None, None

        logger.info(
            "AudioWorker for {}: {:.2f}s".format(
                user_id, time.time() - current_time / 1000
            )
        )

        audio_processor = RealTimeWhisperWithSilenceDetection()
        audio_processor.record(audio_data)
        audio_queue = Queue()

        def wait_for_audio():
            result = audio_processor.audio2text()
            audio_queue.put(result)

        Thread(target=wait_for_audio).start()

        last_word_time = current_time
        while True:
            if not audio_queue.empty():
                text, full_audio = audio_queue.get()
                break
            data = self.pull_audio(user_id)
            if data:
                audio_data = DataParser.parse_voice(data)
                if audio_data is None:
                    continue
                if audio_processor.record(audio_data):
                    last_word_time = DataParser.parse_time(data)

        if full_audio is None:
            return

        if text is None or text == "":
            return

        if not TextHelper.is_speech(text):
            return

        # if VoiceHelper.is_silent(VoiceHelper.bytes2audio(full_audio)):
        #     logger.info("is_silent again for {}".format(user_id))
        #     return

        voice = AuditoryContext(
            current_time=last_word_time,
            user_id=user_id,
            user_text=text,
            user_audio=bytes2bs64(full_audio),
        )

        RedisClientProxy.push_text_data(json.dumps(voice.dict()))

        logger.info(
            "text for {}: {} - cost: {:.2f}s".format(
                user_id, text, time.time() - last_word_time / 1000
            )
        )


while True:
    try:
        users = RedisClientProxy.get_users()
        if len(users) == 0:
            continue
        thread_list = []
        for user in users:
            thread = Thread(
                target=AudioWorker().process,
                args=(user,),
            )
            thread.start()
            thread_list.append(thread)
        for thread in thread_list:
            thread.join()
    except Exception as e:
        logger.error("AudioWorker error: {}, {}".format(e, traceback.format_exc()))
