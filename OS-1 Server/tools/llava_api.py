import json
import random

import requests

from tools.bs64 import image2bs64
from tools.helper import TextHelper
from tools.log import logger

system_prompt = """You are able to understand the visual content that the user provides, and assist the user with a variety of tasks using natural language. Follow the instructions carefully and explain your answers in detail. ###Human: Hi! ###Assistant: Hi there! How can I help you today?\n"""

sep = "###"


class LlavaAPI:
    def __init__(
        self,
        worker_addr=[
            # "http://localhost:40000",
            "http://localhost:40001",
            "http://localhost:40002",
        ],
        model_name="llava-v1.5-7b",
        max_new_tokens=512,
        temperature=0,
        controller_addr="http://localhost:10000",
        use_controller=True,
    ):
        self.worker_addr = worker_addr
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.controller_addr = controller_addr
        self.use_controller = use_controller
        logger.info("LLaVA API initialized.")
        self.workers_get_status()

    def workers_get_status(self):
        response = requests.post(
            url=self.controller_addr + "/worker_get_status",
            headers={"User-Agent": f"LLaVA Client"},
        )
        try:
            res_obj = response.json()
            logger.info(f"Available model_names: {res_obj['model_names']}, speed: {res_obj['speed']}")
        except Exception as e:
            logger.error(f"workers_get_status failed: {e}")
            return None
        return res_obj

    def predict(self, images, message=None, prefix=""):
        prompt = system_prompt
        if message:
            prompt += f"{sep}Human: {message}\n"

        for _ in images:
            prompt += "<image>"

        prompt += f"{sep}Assistant:{prefix}"

        data = {
            "model": self.model_name,
            "prompt": prompt,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "stop": sep,
            "images": images,
        }

        if self.use_controller:
            worker_addr = self.controller_addr
        else:
            worker_addr = random.choice(self.worker_addr)
        url = f"{worker_addr}/worker_generate_stream"
        # print(url)
        response = requests.post(
            url=url,
            headers={"User-Agent": f"LLaVA Client"},
            json=data,
            stream=True,
        )

        output = ""
        for chunk in response.iter_lines(
            chunk_size=8192, decode_unicode=False, delimiter=b"\0"
        ):
            if chunk:
                data = json.loads(chunk.decode("utf-8"))
                output = data["text"].split(sep)[-1]

        return output

    def inference(
        self,
        image,
        message="Describe the scene in brief.",
        prefix="The image shows",
    ):
        return TextHelper.remove_img_prefix(
            self.predict(images=[image2bs64(image)], message=message, prefix=prefix)
        )


LlavaVisualAssistant = LlavaAPI()

if __name__ == "__main__":
    from PIL import Image
    import time

    start = time.time()

    image_path = "../data/images/img_5.jpg"
    image = Image.open(image_path).convert("RGB")

    llava_api = LlavaAPI()

    scene_prompt = """This is a picture taken from my egocentric perspective, please describe 'what I see' in detail."""
    location_prompt = """This is a picture taken from my egocentric perspective, please describe 'where I am' in detail."""
    activity_prompt = """This is a picture taken from my egocentric perspective, please describe 'what I am doing' in detail."""

    caption = llava_api.inference(image=image)
    # scene = llava_api.predict(images=images, message=scene_prompt)
    # location = llava_api.predict(images=images, message=location_prompt)
    # activity = llava_api.predict(images=images, message=activity_prompt)

    print(caption, end="\n")
    # print(scene, end="\n")
    # print(location, end="\n")
    # print(activity, end="\n")

    print(f"Time: {time.time() - start}")
