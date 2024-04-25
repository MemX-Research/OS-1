import http.client
import json
import os
import time

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

from tools.log import logger
from tools.redis_client import RedisClientProxy

accessKeyId = os.getenv("ALI_ACCESS_KEY_ID")
accessKeySecret = os.getenv("ALI_ACCESS_KEY_SECRET")
appKey = os.getenv("ALI_APP_KEY")


class ASRAPI:
    def __init__(self):
        logger.info("Initializing AliASR")

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

    def inference(self, audio_bytes: bytes) -> str:
        host = "nls-gateway-cn-shanghai.aliyuncs.com"
        url = "https://nls-gateway-cn-shanghai.aliyuncs.com/stream/v1/asr"

        format = "pcm"
        sampleRate = 16000
        enablePunctuationPrediction = True
        enableInverseTextNormalization = True
        enableVoiceDetection = False

        # 设置RESTful请求参数
        request = url + "?appkey=" + appKey
        request = request + "&format=" + format
        request = request + "&sample_rate=" + str(sampleRate)

        if enablePunctuationPrediction:
            request = request + "&enable_punctuation_prediction=" + "true"

        if enableInverseTextNormalization:
            request = request + "&enable_inverse_text_normalization=" + "true"

        if enableVoiceDetection:
            request = request + "&enable_voice_detection=" + "true"

        token = self.get_token().decode("utf-8")

        headers = {
            "X-NLS-Token": token,
            "Content-type": "application/octet-stream",
            "Content-Length": len(audio_bytes),
        }

        conn = http.client.HTTPSConnection(host)
        conn.request(method="POST", url=request, body=audio_bytes, headers=headers)

        response = conn.getresponse()

        body = response.read()
        result = ""
        try:
            print("Recognize response is:")
            body = json.loads(body)
            print(body)

            status = body["status"]
            if status == 20000000:
                result = body["result"]
                print("Recognize result: " + result)
            else:
                result = ""
                print("Recognizer failed!")

        except ValueError:
            logger.error("The response is not json format string")

        conn.close()

        return result


ASRAPITool = ASRAPI()

if __name__ == "__main__":
    pass
    # audio_processor = RealTimeWhisperWithSilenceDetection()
    # for i in range(5):
    #     audio_data = f"../data/audios/zh_{i}.mp3"
    #     sound = AudioSegment.from_file(audio_data, format="mp3")
    #     output = io.BytesIO()
    #     sound.export(output, format="wav")
    #     wav_data = AudioSegment.from_wav(output)
    #     audio_processor.record(wav_data)
    #     # res = audio_processor.is_voice(wav_data)
    #     # print(f"res: {res}")
    # text, _ = audio_processor.audio2text()
    # print(text)
