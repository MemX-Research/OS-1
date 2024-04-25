import requests
from PIL import Image

from tools.bs64 import image2bs64
from tools.log import logger


class ImageCaptioning:
    def __init__(self, url="http://127.0.0.1:7891"):
        self.base_url = url + "/run/predict"
        logger.info("Initializing BLIP2 ImageCaptioning via %s" % url)

    def inference(self, image: Image) -> str:
        image_bs64 = image2bs64(image)
        data = {
            "data": [
                f"data:image/png;base64,{image_bs64}",
                "Image Captioning",
                "",
            ]
        }
        response = requests.post(self.base_url, json=data).json()["data"]
        captions = response[0]
        return captions


class VisualQuestionAnswering:
    def __init__(self, url="http://127.0.0.1:7891"):
        self.base_url = url + "/run/predict"
        logger.info("Initializing BLIP2 VQA via %s" % url)

    def inference(self, image: Image, question: str) -> str:
        image_bs64 = image2bs64(image)
        data = {
            "data": [
                f"data:image/png;base64,{image_bs64}",
                "Visual Question Answering",
                f"{question}",
            ]
        }
        response = requests.post(self.base_url, json=data).json()["data"]
        captions = response[0]
        return captions


# ImageCaptionTool = ImageCaptioning()
# VQATool = VisualQuestionAnswering()
