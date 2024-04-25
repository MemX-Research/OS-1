import datetime
import json
import re

from base.memorizer import Memory, MemoryType
from templates.memory import (
    MEMORY_IMPORTANCE_PROMPT,
    EMOTIONAL_AROUSAL_PROMPT,
    MEMORY_POINT_PROMPT,
)
from tools.llm import ChatModel
from tools.log import logger
from tools.openai_api import get_openai_chatgpt
from tools.time_fmt import get_timestamp


class MemoryEvaluator:
    def __init__(self, user_id: str):
        self.user_id = user_id

    @classmethod
    def generate_importance(cls, memory: Memory) -> int:
        # score: 1 to 10
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                pl_tags=[
                    "memory-importance",
                    memory.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        system_prompt = MEMORY_IMPORTANCE_PROMPT.format(
            memory=memory.content,
        )

        res = chat_model.predict_with_prompt(prompt=system_prompt)

        pattern = re.compile(r"\d+")
        score = int(pattern.findall(res)[0])
        logger.info(
            f"generate memory importance score: {score}, content: {memory.content}"
        )
        return score


class MemoryEvaluatorWithEmotion:
    def __init__(self, user_id: str):
        self.user_id = user_id

    @classmethod
    def generate_importance(cls, memory: Memory) -> dict:
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                pl_tags=[
                    "memory-emotion-arousal",
                    memory.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        detail = memory.detail if memory.detail is not None else memory.content

        system_prompt = EMOTIONAL_AROUSAL_PROMPT.format(detail=detail)

        res = chat_model.predict_with_prompt(prompt=system_prompt)

        logger.info(f"generate memory emotion arousal: {res}, detail: {detail}")

        return json.loads(res)


class MemoryEvaluatorWithIndex:
    def __init__(self, user_id: str):
        self.user_id = user_id

    @classmethod
    def generate_index(cls, memory: Memory) -> dict:
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                pl_tags=[
                    "memory-index",
                    memory.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        if memory.detail is None:
            system_prompt = MEMORY_POINT_PROMPT.format(
                detail=memory.content,
            )
        else:
            system_prompt = MEMORY_POINT_PROMPT.format(detail=memory.detail)

        res = chat_model.predict_with_prompt(prompt=system_prompt)

        return json.loads(res)


if __name__ == "__main__":
    # mems = Memory.get_memory_by_duration(
    #     memory_type=MemoryType.ONE_MINUTE,
    #     user_id="new-mem",
    #     start=0,
    #     end=get_timestamp(),
    #     limit=1,
    # )
    # for mem in mems:
    #     mem = Memory.parse_obj(mem)
    #     res = MemoryEvaluatorWithEmotion.generate_importance(mem)
    #     print(res)
    #
    # mems = Memory.get_memory_by_duration(
    #     memory_type=MemoryType.CONVERSATION,
    #     user_id="new-mem",
    #     start=0,
    #     end=get_timestamp(),
    #     limit=1,
    # )
    # for mem in mems:
    #     mem = Memory.parse_obj(mem)
    #     res = MemoryEvaluatorWithEmotion.generate_importance(mem)
    #     print(res)

    mems = Memory.get_memory_by_duration(
        memory_type=MemoryType.ONE_DAY,
        user_id="new-mem",
        start=0,
        end=get_timestamp(),
        limit=1,
    )
    for mem in mems:
        mem = Memory.parse_obj(mem)
        res = MemoryEvaluatorWithIndex.generate_index(mem)
        print(res)

    mems = Memory.get_memory_by_duration(
        memory_type=MemoryType.CONVERSATION,
        user_id="new-mem",
        start=0,
        end=get_timestamp(),
        limit=1,
    )
    for mem in mems:
        mem = Memory.parse_obj(mem)
        res = MemoryEvaluatorWithIndex.generate_index(mem)
        print(res)
