import requests
from tools.log import logger


class TTSAPI:
    def __init__(self, url="http://127.0.0.1:7892"):
        self.base_url = url + "/run/predict"
        logger.info("Initializing TTS via %s" % url)

    def inference(self, text: str) -> str:
        data = {
            "data": [
                text,
            ]
        }
        response = requests.post(self.base_url, json=data).json()["data"]
        return f"data:audio/wav;base64,{response[0]}"


TTSAPITool = TTSAPI()

if __name__ == "__main__":
    import time
    from gradio.components import processing_utils

    start = time.time()
    res = TTSAPITool.inference("你好，我是Samantha，很高兴认识你，有什么可以帮助你的吗？")
    print(time.time() - start)
    wav_file = open("tmp.wav", "wb")
    wav_file.write(processing_utils.decode_base64_to_binary(encoding=res)[0])
