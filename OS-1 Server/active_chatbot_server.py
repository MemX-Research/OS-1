import json
import time
import traceback
from threading import Thread

from core.active import ActiveSpeakerWithAttention
from tools.log import logger
from tools.redis_client import RedisClientProxy


class ActiveChatbotWorker:
    @staticmethod
    def pull_text():
        data = RedisClientProxy.pop_text_data()
        if data is None:
            return None
        return json.loads(data)

    def process(self, user_id):
        ActiveSpeakerWithAttention(user_id=user_id).active_conversation()


while True:
    try:
        users = RedisClientProxy.get_users()
        if len(users) == 0:
            continue
        thread_list = []
        for user in users:
            thread = Thread(
                target=ActiveChatbotWorker().process,
                args=(user,),
            )
            thread.start()
            thread_list.append(thread)
        for thread in thread_list:
            thread.join()
        time.sleep(3)
    except Exception as e:
        logger.error(
            "ActiveChatbotWorker error: {}, {}".format(e, traceback.format_exc())
        )
