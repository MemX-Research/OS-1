import time
from typing import Any

import pymongo

from tools.time_fmt import get_past_timestamp


class MongoClient:
    def __init__(self, host="localhost", port=27017):
        self.mongo_client = pymongo.MongoClient(host=host, port=port)

    def get_client(self):
        return self.mongo_client

    def get_users(self):
        return self.mongo_client["memx"]["conversation"].distinct("user_id")

    def get_context_active_users(self):
        return self.mongo_client["memx"]["context"].distinct(
            key="user_id",
            filter={
                "current_time": {
                    "$gte": get_past_timestamp(),
                },
            },
        )

    def get_conversation_active_users(self):
        return self.mongo_client["memx"]["conversation"].distinct(
            key="user_id",
            filter={
                "current_time": {
                    "$gte": get_past_timestamp(),
                },
            },
        )

    def save_context(self, data):
        return self.mongo_client["memx"]["context"].insert_one(data)

    def save_context_minutes(self, data):
        return self.mongo_client["memx"]["context_minutes"].insert_one(data)

    def find_context(self, user_id: str):
        return (
            self.mongo_client["memx"]["context"]
            .find(
                {"user_id": user_id},
                {
                    "original_image": 0,
                    "attended_image": 0,
                    "visual_image": 0,
                    "gaze_point": 0,
                    "_id": 0,
                },
            )
            .sort("current_time", pymongo.DESCENDING)
            .limit(5)
        )

    def find_contexts(self, *args: Any, **kwargs: Any):
        return self.mongo_client["memx"]["context"].find(*args, **kwargs)

    def save_history(self, data):
        return self.mongo_client["memx"]["history"].insert_one(data)

    def find_history(self, user_id: str):
        return (
            self.mongo_client["memx"]["history"]
            .find({"user_id": user_id})
            .sort("current_time", pymongo.DESCENDING)
            .limit(1)
        )

    def find_histories(self, *args: Any, **kwargs: Any):
        return self.mongo_client["memx"]["history"].find(*args, **kwargs)

    def _save_conversation(self, data):
        return self.mongo_client["memx"]["conversation"].insert_one(data)

    def _find_conversation(self, user_id: str):
        return (
            self.mongo_client["memx"]["conversation"]
            .find(
                {"user_id": user_id},
                {"_id": 0, "audio": 0, "prompt": 0},
            )
            .sort("current_time", pymongo.DESCENDING)
            .limit(8)
        )

    def _find_conversations(self, *args: Any, **kwargs: Any):
        return self.mongo_client["memx"]["conversation"].find(*args, **kwargs)

    def get_latest_context(self, user_id: str, seconds: int = 300, limit: int = 10):
        timestamp = int(round(time.time() * 1000))
        res = (
            self.find_contexts(
                {
                    "user_id": user_id,
                    "current_time": {
                        "$gte": timestamp - 1000 * seconds,
                        "$lte": timestamp,
                    },
                },
                {
                    "original_image": 0,
                    "attended_image": 0,
                    "visual_image": 0,
                    "gaze_point": 0,
                    "_id": 0,
                },
            )
            .sort("current_time", pymongo.DESCENDING)
            .limit(limit)
        )
        res = list(res)
        res.reverse()
        return res


    
    def get_collection(self, collection_name: str):
        return self.mongo_client["memx"][collection_name]


MongoClientProxy = MongoClient()

if __name__ == "__main__":
    print(MongoClientProxy.get_context_active_users())
    print(MongoClientProxy.get_conversation_active_users())

    def get_all_context(user_id):
        res = MongoClientProxy.find_contexts(
            {
                "user_id": user_id,
            },
            {
                "original_image": 0,
                "attended_image": 0,
                "visual_image": 0,
                "gaze_point": 0,
                "_id": 0,
            },
        ).sort("current_time", pymongo.ASCENDING)
        return list(res)

    def get_all_conversation(user_id):
        res = MongoClientProxy._find_conversations(
            {
                "user_id": user_id,
            },
            {"_id": 0, "audio": 0, "prompt": 0},
        ).sort("current_time", pymongo.ASCENDING)
        return list(res)

    def context_str(res):
        contexts = []
        for item in res:
            context_list = []
            if item["current_time"] is not None:
                context_list.append(
                    f'Time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["current_time"] / 1000))}'
                )
            if item["location"] is not None:
                context_list.append(f'Location: {item["location"]}')
            if item["scene"] is not None:
                context_list.append(f'Scene: {item["scene"]}')
            if item["attention"] is not None:
                context_list.append(f'Attention: {item["attention"]}')
            if item["activity"] is not None:
                context_list.append(f'Activity: {item["activity"]}')
            contexts.append(" ".join(context_list))
        return "\n".join(contexts)

    users = MongoClientProxy.get_users()
    for user in users:
        all_context = get_all_context(user)
        all_conversation = get_all_conversation(user)
        if len(all_context) < 200 or len(all_conversation) < 30:
            continue
        print(
            f"{user}, context: {len(all_context)}, conversation: {len(all_conversation)}"
        )
        if user != "hyln-memory":
            continue

        for context in all_context:
            ctx = context_str([context])
            if "white background" in ctx or "white picture" in ctx:
                continue
            print(ctx)
