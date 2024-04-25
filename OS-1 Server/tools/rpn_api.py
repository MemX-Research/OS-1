import json
from typing import List

import requests
from PIL import Image

from tools.bs64 import image2bs64
from tools.log import logger


class RPNAttention:
    def __init__(self, url="http://127.0.0.1:7862"):
        self.base_url = url + "/run/predict"
        logger.info("Initializing RPN via %s" % url)

    def inference(self, image: Image, gaze_x, gaze_y) -> List:
        image_bs64 = image2bs64(image)
        data = {
            "data": [
                f"data:image/png;base64,{image_bs64}",
                gaze_x,
                gaze_y,
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


RPNAttentionTool = RPNAttention()
