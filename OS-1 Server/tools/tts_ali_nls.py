import http.client
import io
import json
import os
import time

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from pydub import AudioSegment

from tools.bs64 import bytes2bs64
from tools.log import logger
from tools.redis_client import RedisClientProxy

from xml.etree import ElementTree as ET

accessKeyId = os.getenv("ALI_ACCESS_KEY_ID")
accessKeySecret = os.getenv("ALI_ACCESS_KEY_SECRET")
appKey = os.getenv("ALI_APP_KEY")

EMOTION_LIST = [
    "serious",
    "sad",
    "disgust",
    "jealousy",
    "embarrassed",
    "happy",
    "fear",
    "surprise",
    "neutral",
    "frustrated",
    "affectionate",
    "gentle",
    "angry",
]


class TTSAPI:
    def __init__(self):
        logger.info("Initializing AliTTS")

    @staticmethod
    def get_token():
        if not (
            int(time.time())
            > int(RedisClientProxy.get("aliyun_nls_token_expire_time") or 0)
        ):
            return RedisClientProxy.get("aliyun_nls_token")

        client = AcsClient(accessKeyId, accessKeySecret, "cn-shanghai")

        request = CommonRequest()
        request.set_method("POST")
        request.set_domain("nls-meta.cn-shanghai.aliyuncs.com")
        request.set_version("2019-02-28")
        request.set_action_name("CreateToken")

        try:
            response = client.do_action_with_exception(request)

            jss = json.loads(response)
            if "Token" in jss and "Id" in jss["Token"]:
                RedisClientProxy.set("aliyun_nls_token", jss["Token"]["Id"])
                RedisClientProxy.set(
                    "aliyun_nls_token_expire_time", jss["Token"]["ExpireTime"]
                )
        except Exception as e:
            logger.error("Ali get token error: %s" % e)

    def inference(self, text, emotion="", format="wav", sampleRate=8000):
        host = "nls-gateway-cn-shanghai.aliyuncs.com"
        url = "https://nls-gateway-cn-shanghai.aliyuncs.com/stream/v1/tts"
        token = self.get_token().decode("utf-8")
        headers = {"Content-Type": "application/json"}

        ssml_text = self.get_ssml_text(text, emotion)
        body = json.dumps(
            {
                "token": token,
                "appkey": appKey,
                "text": ssml_text,
                "format": format,
                "sample_rate": sampleRate,
            }
        )

        conn = http.client.HTTPSConnection(host)
        conn.request(method="POST", url=url, body=body, headers=headers)

        response = conn.getresponse()
        contentType = response.getheader("Content-Type")

        response = response.read()
        conn.close()

        if "audio/mpeg" == contentType:
            return "data:audio/wav;base64," + bytes2bs64(
                AudioSegment.from_file(
                    io.BytesIO(response),
                    format="wav",
                    sample_width=2,
                    frame_rate=8000,
                    channels=1,
                )
                .export(format="wav")
                .read()
            )

        logger.error("AliTTS get audio error: %s" % response.decode("utf-8"))
        return ""

    def get_ssml_text(self, text, emotion) -> str:
        if emotion:
            emotion = emotion.lower().strip()
        if not emotion or emotion not in EMOTION_LIST:
            emotion = "neutral"

        root = ET.Element("speak")
        emotion_tag = ET.SubElement(root, "emotion")
        emotion_tag.text = text
        emotion_tag.set("category", emotion)

        return ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")


TTSAPITool = TTSAPI()

if __name__ == "__main__":
    from gradio.components import processing_utils

    start = time.time()
    res = TTSAPITool.inference("你好，我是Samantha，很高兴认识你，有什么可以帮助你的吗？", "sad")
    # print(res)
    print(time.time() - start)
    wav_file = open("tmp.wav", "wb")
    wav_file.write(processing_utils.to_binary(res))
