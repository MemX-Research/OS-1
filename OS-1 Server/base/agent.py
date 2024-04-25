from typing import Any
from typing import Optional, List

import pymongo

from base.tag import Tag
from tools.mongo import MongoClientProxy
from tools.time_fmt import get_timestamp


class Policy(Tag):
    policy_plan: Optional[str]
    policy_action: Optional[str]

    def save_policy(self):
        return MongoClientProxy.get_client()["memx"]["policy"].insert_one(self.dict())

    @staticmethod
    def find_policies(*args: Any, **kwargs: Any):
        return MongoClientProxy.get_client()["memx"]["policy"].find(*args, **kwargs)

    @classmethod
    def get_latest_policy(
        cls,
        user_id: str,
        seconds: int = 600,
        limit: int = 1,
        end: Optional[int] = None,
    ):
        if end is None:
            end = get_timestamp()
        res = (
            cls.find_policies(
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


class Query(Tag):
    query_plan: Optional[List[str]]
    query_detail: Optional[dict] = dict()
    query_report: Optional[str]

    def save_query(self):
        return MongoClientProxy.get_client()["memx"]["query"].insert_one(self.dict())

    @staticmethod
    def find_queries(*args: Any, **kwargs: Any):
        return MongoClientProxy.get_client()["memx"]["query"].find(*args, **kwargs)

    @classmethod
    def get_latest_queries(
        cls,
        user_id: str,
        seconds: int = 600,
        limit: int = 1,
        end: Optional[int] = None,
    ):
        if end is None:
            end = get_timestamp()
        res = (
            cls.find_queries(
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
