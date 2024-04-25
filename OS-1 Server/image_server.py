import json
import traceback
from multiprocessing import Process

from base.parser import DataParser
from base.visual import VisualImage
from core.visual import VisualContextRecognizer
from tools.log import logger
from tools.redis_client import RedisClientProxy


class ImageWorker:
    def __init__(self, visual_context_recognizer=VisualContextRecognizer()):
        self.visual_context_recognizer = visual_context_recognizer
        logger.info("ImageWorker init")

    @staticmethod
    def pull_image():
        data = RedisClientProxy.pop_image_data()
        if data is None:
            return None
        return json.loads(data)

    def create_visual_image(self, data):
        visual_image = VisualImage(
            current_time=DataParser.parse_time(data),
            user_id=DataParser.parse_uid(data),
            original_image=DataParser.parse_image(data),
            gaze_point=DataParser.parse_gaze(data),
        )
        if visual_image.original_image is None or visual_image.gaze_point is None:
            return None
        return visual_image

    def process(self):
        while True:
            try:
                data = self.pull_image()
                if data is None:
                    continue
                visual_image = self.create_visual_image(data)
                if visual_image is None:
                    continue
                visual_context = self.visual_context_recognizer.recognize_context_with_conversation(
                    visual_image
                )
                if visual_context.scene == "":
                    logger.warning(
                        "Empty scene for {}".format(visual_context.user_id)
                    )
                    continue
                visual_context.save_context()
            except Exception as e:
                logger.error(
                    "ImageWorker error: {}, {}".format(e, traceback.format_exc())
                )


num_workers = 2
thread_list = []
for _ in range(num_workers):
    thread = Process(target=ImageWorker().process)
    thread.start()
    thread_list.append(thread)
[thread.join() for thread in thread_list]
