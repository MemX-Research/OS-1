from abc import ABCMeta, abstractmethod
from typing import Optional, Any, Tuple

import pymongo
from PIL.Image import Image

from base.tag import Tag
from tools.helper import TextHelper
from tools.mongo import MongoClientProxy
from tools.time_fmt import get_relative_time, get_timestamp, timestamp_to_str


class VisualImage(Tag):
    original_image: Image = None
    attended_image: Image = None
    visual_image: Image = None
    gaze_point: Optional[Tuple[float, float]] = None


class VisualContext(Tag):
    original_image: Optional[str] = None
    attended_image: Optional[str] = None
    visual_image: Optional[str] = None
    gaze_point: Optional[Tuple[float, float]] = None

    scene: Optional[str] = None
    attention: Optional[str] = None
    location: Optional[str] = None
    activity: Optional[str] = None
    emotion: Optional[str] = None

    def format(self, absolute_time=False, now=None):
        context = []
        if self.current_time is not None:
            if absolute_time:
                context.append(timestamp_to_str(self.current_time))
            else:
                context.append(get_relative_time(self.current_time, now=now))
        if self.location is not None:
            context.append(f"We are in: {self.location}")
        if self.scene is not None:
            self.scene = TextHelper.remove_img_prefix(self.scene)
            context.append(f"We can see: {self.scene}")
        # if self.attention is not None:
        #     self.attention = TextHelper.remove_img_prefix(self.attention)
        #     context.append(f"I fixate on: {self.attention}")
        if self.activity is not None:
            context.append(f"My Friend may be {self.activity}")
        if self.emotion is not None:
            context.append(f"It looks like my friend is {self.emotion}")
        # empty context (only contains time)
        if len(context) == 1 and self.current_time is not None:
            context.append("I did not noticing anything special in my sight. I should focus on my human friend's words.")
        return " ".join(context)

    @classmethod
    def format_list(cls, res, absolute_time=False, now=None):
        contexts = [
            cls.parse_obj(item).format(absolute_time=absolute_time, now=now) for item in res
        ]
        return "\n".join(contexts)

    def save_context(self):
        return MongoClientProxy.get_client()["memx"]["context"].insert_one(self.dict())

    @staticmethod
    def find_contexts(*args: Any, **kwargs: Any):
        return MongoClientProxy.get_client()["memx"]["context"].find(*args, **kwargs)

    @classmethod
    def get_contexts_by_duration(
        cls, user_id: str, start: int, end: int, limit: int = 10, sort=pymongo.DESCENDING
    ):
        res = list(
            cls.find_contexts(
                {
                    "user_id": user_id,
                    "current_time": {
                        "$gte": start,
                        "$lte": end,
                    },
                },
                {
                    "original_image": 0,
                    "attended_image": 0,
                    "visual_image": 0,
                    "gaze_point": 0,
                },
            )
            .sort("current_time", sort)
            .limit(limit)
        )
        res.reverse()
        return res

    @classmethod
    def get_latest_context(cls, user_id: str, seconds: int = 300, limit: int = 10, end=None):
        if end is None:
            end = get_timestamp()
        start = end - 1000 * seconds
        return cls.get_contexts_by_duration(user_id, start, end, limit)


class VisualPerceptron(metaclass=ABCMeta):
    @abstractmethod
    def recognize_context(self, visual_image: VisualImage) -> VisualContext:
        pass


if __name__ == "__main__":
    res = VisualContext().get_latest_context("f9862d48510003b3", seconds=9999999999)
    print(res)
    print(len(res))
