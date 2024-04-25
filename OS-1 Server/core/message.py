import json
import time
from typing import Optional

from base.message import Message, MessageSender, VoiceGenerator
from tools.log import logger
from tools.redis_client import RedisClientProxy
from tools.time_fmt import get_timestamp

# from tools.tts_api import TTSAPITool
from tools.tts_ali_nls import TTSAPITool


class VoiceGeneratorWithTTS(VoiceGenerator):
    def generate_voice(self, msg: Message) -> Optional[Message]:
        msg.voice = TTSAPITool.inference(msg.text, emotion=msg.emotion)
        logger.info(
            "generate_voice for {}: {}, {:.2f}s".format(
                msg.user_id, msg.text, time.time() - msg.current_time / 1000
            )
        )
        return msg


class MessageSenderWithRedis(MessageSender):
    def send_message(self, msg: Message, extra: Optional[dict]=None):
        response = {
            "message": {
                "start_time": msg.start_time,
                "text": msg.text,
                "voice": msg.voice,
            }
        }
        if extra is not None:
            response["extra"] = extra
        RedisClientProxy.push_msg(msg.user_id, json.dumps(response), timeout=120)
        logger.info(
            "send_message for {}: {}, {:.2f}s".format(
                msg.user_id, msg.text, time.time() - msg.current_time / 1000
            )
        )


if __name__ == "__main__":
    msg = Message(
        user_id="test",
        current_time=get_timestamp(),
        text="<User>: Hello, what can I do for you?",
    )
    msg = VoiceGeneratorWithTTS().generate_voice(msg)
    print(msg.voice)
    print(len(msg.voice))
    MessageSenderWithRedis().send_message(msg)
