import requests

from tools.bs64 import bytes2bs64
from tools.log import logger


class VoiceActivityAPI:
    def __init__(self, url="http://127.0.0.1:7894"):
        self.base_url = url + "/run/predict"
        logger.info("Initializing VoiceActivityAPI via %s" % url)

    def is_voice(self, audio_bytes: bytes) -> bool:
        base64_str = bytes2bs64(audio_bytes)
        data = {
            "data": [
                {"name": "audio.wav", "data": f"data:audio/wav;base64,{base64_str}"},
            ]
        }
        response = requests.post(self.base_url, json=data).json()

        res = False
        if response["data"][0] == "1":
            res = True
        logger.info(
            "VoiceActivity api: is_voice:{},{:.2f}s".format(res, response["duration"])
        )
        return res


ASRVoiceActivityAPI = VoiceActivityAPI()
