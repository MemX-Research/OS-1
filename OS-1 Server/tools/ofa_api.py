import json
from typing import List

import requests
from PIL import Image

from tools.bs64 import image2bs64
from tools.log import logger


class ImageCaptioning:
    def __init__(self, url="http://127.0.0.1:7860"):
        self.base_url = url + "/run/predict"
        logger.info("Initializing OFA ImageCaptioning via %s" % url)

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
        captions = response[1]
        return captions


class VisualQuestionAnswering:
    def __init__(self, url="http://127.0.0.1:7860"):
        self.base_url = url + "/run/predict"
        logger.info("Initializing OFA VQA via %s" % url)

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
        captions = response[1]
        return captions


class VisualGrounding:
    def __init__(self, url="http://127.0.0.1:7860"):
        self.base_url = url + "/run/predict"
        logger.info("Initializing OFA Visual Grounding via %s" % url)

    def inference(self, image: Image, question="object next to the red circle") -> List:
        template = f'which region does the text "{question}" describe?'
        image_bs64 = image2bs64(image)
        data = {
            "data": [
                f"data:image/png;base64,{image_bs64}",
                "Visual Question Answering",
                f"{template}",
            ]
        }
        response = requests.post(self.base_url, json=data).json()["data"]
        coords_str = response[1]  # bbox坐标[x0,y0,x1,y1]
        try:
            coords = json.loads(coords_str)
        except Exception as e:
            print("no <bin> found", e)
            coords = [0, 0, 0, 0]
        return coords


# ImageCaptionTool = ImageCaptioning()
# VQATool = VisualQuestionAnswering()
# VisualGroundingTool = VisualGrounding()
