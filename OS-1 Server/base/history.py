from abc import ABCMeta, abstractmethod
from typing import Any
from typing import Optional

import pymongo

from base.tag import Tag, BaseModel
from tools.mongo import MongoClientProxy
from tools.time_fmt import get_timestamp


class HumanProfile(BaseModel):
    # name: Optional[str] = None
    personality: Optional[str] = ""
    job: Optional[str] = ""
    lifestyle: Optional[str] = ""

    like: Optional[str] = ""
    dislike: Optional[str] = ""
    emotion: Optional[str] = ""
    intention: Optional[str] = ""
    need: Optional[str] = ""


class AIProfile(BaseModel):
    personality: Optional[str] = ""
    like: Optional[str] = ""
    dislike: Optional[str] = ""


class History(Tag):
    human_profile: Optional[HumanProfile] = HumanProfile()
    ai_profile: Optional[AIProfile] = AIProfile()

    def save_history(self):
        return MongoClientProxy.get_client()["memx"]["history"].insert_one(self.dict())

    @staticmethod
    def find_histories(*args: Any, **kwargs: Any):
        return MongoClientProxy.get_client()["memx"]["history"].find(*args, **kwargs)

    @classmethod
    def get_latest_history(
            cls,
            user_id: str,
            seconds: int = 604800,
            limit: int = 1,
            end: Optional[int] = None
    ):
        if end is None:
            end = get_timestamp()
        res = (
            cls.find_histories(
                {
                    "user_id": user_id,
                    "current_time": {
                        "$gte": end - 1000 * seconds,
                        "$lte": end,
                    },
                },
            )
            .sort("current_time", pymongo.DESCENDING)
            .limit(limit)
        )
        res = list(res)
        res.reverse()
        return res


class HistoryGenerator(metaclass=ABCMeta):
    @abstractmethod
    def generate_history(self):
        pass
