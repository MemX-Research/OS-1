import json
import traceback
from threading import Thread

from base.parser import DataParser
from tools.ali_asr_api import AliRealTimeASR
from tools.log import logger
from tools.redis_client import RedisClientProxy


class AudioWorker:
    def __init__(self, user_id):
        self.user_id = user_id
        self.asr = AliRealTimeASR(uid=user_id)

    def pull_audio(self):
        data = RedisClientProxy.pop_audio_data(self.user_id)
        if data is None:
            return None
        return json.loads(data)

    def process(self):
        while True:
            try:
                data = self.pull_audio()
                if data is None:
                    continue

                audio_data = DataParser.parse_voice_bytes(data)
                if audio_data is None:
                    continue

                self.asr.push_audio(audio_data, self.user_id)

            except Exception as e:
                self.asr = AliRealTimeASR(uid=self.user_id)
                logger.error(
                    "AudioWorker error for {}: {}, {}".format(
                        self.user_id, e, traceback.format_exc()
                    )
                )


user_map = dict()
while True:
    try:
        users = RedisClientProxy.get_users()
        if len(users) == 0:
            continue
        for user in users:
            if user in user_map:
                continue
            audio_worker = AudioWorker(user_id=user)
            user_map[user] = audio_worker
            logger.info("new user: {}".format(user))
            Thread(target=audio_worker.process).start()
    except Exception as e:
        logger.error("AudioWorker error: {}, {}".format(e, traceback.format_exc()))
