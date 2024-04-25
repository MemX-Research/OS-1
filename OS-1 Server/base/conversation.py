from typing import List, Optional, Any

import pymongo
from bson import json_util
from langchain.prompts.chat import (
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
    BaseStringMessagePromptTemplate,
)

from base.tag import Tag
from tools.authorization import UserController, User
from tools.mongo import MongoClientProxy
from tools.time_fmt import get_timestamp


class Conversation(Tag):
    human: Optional[str] = None
    ai: Optional[str] = None
    context_id: Optional[str] = None
    history_id: Optional[str] = None
    audio: Optional[str] = None
    prompt: Optional[str] = None
    is_encrypted: Optional[bool] = False

    def encrypted_dict(self):
        user = UserController().get_user(self.user_id)
        if user is None:
            return self.dict()
        else:
            return {
                **self.dict(),
                "human": user.encrypt_msg(self.human),
                "ai": user.encrypt_msg(self.ai),
                "prompt": user.encrypt_msg(self.prompt),
                "is_encrypted": True,
            }

    @staticmethod
    def decrypted_dict(item):
        if "is_encrypted" in item and item["is_encrypted"]:
            user = UserController().get_user(item["user_id"])
            if user is None:
                return item
            else:
                return {
                    **item,
                    "human": user.decrypt_msg(item.get("human", "")),
                    "ai": user.decrypt_msg(item.get("ai", "")),
                    "prompt": user.decrypt_msg(item.get("prompt", "")),
                    "is_encrypted": False,
                }
        return item

    def save_conversation(self):
        return MongoClientProxy.get_client()["memx"]["conversation"].insert_one(
            self.encrypted_dict()
        )

    @staticmethod
    def find_conversations(*args: Any, **kwargs: Any):
        res_list = MongoClientProxy.get_client()["memx"]["conversation"].find(
            *args, **kwargs
        )
        for item in res_list:
            # decrypt
            yield Conversation.decrypted_dict(item)
  

    @classmethod
    def get_conversation_by_duration(
        cls, user_id: str, start: int, end: int, limit: int = 10
    ):
        res = list(
            cls.find_conversations(
                {
                    "user_id": user_id,
                    "current_time": {
                        "$gte": start,
                        "$lte": end,
                    },
                },
                {"_id": 0, "audio": 0, "prompt": 0},
                sort=[("current_time", pymongo.DESCENDING)],
                limit=limit,
            )
        )
        res.reverse()
        return res

    @classmethod
    def get_latest_conversation(
        cls,
        user_id: str,
        seconds: int = 1800,
        limit: int = 3,
        end: Optional[int] = None,
    ):
        if end is None:
            end = get_timestamp()
        start = end - 1000 * seconds
        return cls.get_conversation_by_duration(user_id, start, end, limit)

    def format(self):
        chat_msgs = []
        if self.human is not None:
            if self.human == "":
                self.human = "(No response)"
            chat_msgs.append(
                # HumanMessagePromptTemplate.from_template(
                #     self.human, additional_kwargs={"name": "Friend"}
                # )
                HumanMessagePromptTemplate.from_template(self.human)
            )
        if self.ai is not None:
            chat_msgs.append(
                # AIMessagePromptTemplate.from_template(
                #     self.ai, additional_kwargs={"name": "Samantha"}
                # )
                AIMessagePromptTemplate.from_template(self.ai)
            )
        return chat_msgs

    @classmethod
    def format_list(cls, res):
        conversations = []
        for item in res:
            item["history_id"] = ""
            conversations += cls.parse_raw(
                json_util.dumps(item), allow_pickle=True
            ).format()
        return conversations

    @staticmethod
    def msgs_to_string(
        msgs: List[BaseStringMessagePromptTemplate],
        human_prefix="Human",
        ai_prefix="Samantha",
    ):
        res_str = ""
        for item in msgs:
            item = item.format()
            if item.type == "human":
                res_str += f"{human_prefix}: {item.content}\n"
            elif item.type == "ai":
                res_str += f"{ai_prefix}: {item.content}\n"

        return res_str


if __name__ == "__main__":
    res = Conversation().get_latest_conversation(
        user_id="new-mem", seconds=60 * 60 * 24, limit=0
    )
    print(res)
    print(len(res))
    for item in res:
        conv = Conversation.parse_obj(item)
        print(f"User: {conv.human}")
        print(f"Samantha: {conv.ai}")
