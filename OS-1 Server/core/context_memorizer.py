import datetime
import json
import traceback
from typing import List

from langchain.prompts import PromptTemplate

from base.memorizer import Memory
from base.memorizer import MemoryGenerator
from base.memorizer import MemoryType, get_duration
from base.visual import VisualContext
from core.memory_evaluator import (
    MemoryEvaluator,
    MemoryEvaluatorWithEmotion,
    MemoryEvaluatorWithIndex,
)
from templates.event import (
    CONTEXT_EVENT_SUMMARY_PROMPT,
    CONTEXT_EVENT_PROMPT,
)
from templates.prompt import CONTEXT_MEMORY_PROMPT
from tools.llm import ChatModel
from tools.log import logger
from tools.openai_api import get_openai_chatgpt
from tools.similarity import text_cluster
from tools.time_fmt import get_timestamp
from tools.time_fmt import str_to_timestamp, timestamp_to_str


class MemoryGeneratorForContext(MemoryGenerator):
    """deprecated"""

    def __init__(self, user_id: str, start_date: int, end_date: int):
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    @staticmethod
    def summarize_context(user_id: str, prompt: str):
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.5,
                pl_tags=[
                    "context-memorizer",
                    user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )
        res = chat_model.predict_with_prompt(prompt=prompt)
        return json.loads(res)

    @classmethod
    def summarize_context_with_saving(
        cls,
        user_id: str,
        start_ts: int,
        end_ts: int,
        prompt: str,
        memory_type: MemoryType,
    ):
        res = cls.summarize_context(
            user_id=user_id,
            prompt=prompt,
        )

        memory = Memory(
            current_time=get_timestamp(),
            memory_type=memory_type.value,
            start_time=start_ts,
            end_time=end_ts,
            user_id=user_id,
            content=res["memory"],
        )
        memory.importance = MemoryEvaluator.generate_importance(memory) / 10
        memory.save_memory()
        memory.save_memory_to_vectordb()

        logger.info(
            f"generate context memory for {user_id} in {timestamp_to_str(start_ts)} - {timestamp_to_str(end_ts)}: {res}"
        )

    @classmethod
    def generate_context_summary(
        cls,
        user_id: str,
        start_ts: int,
        end_ts: int,
        old_type: MemoryType,
        new_type: MemoryType,
        prompt: PromptTemplate,
        limit: int = 10,
    ):
        res = Memory.get_memory_by_duration(
            memory_type=old_type,
            user_id=user_id,
            start=start_ts,
            end=end_ts,
            limit=limit,
        )

        if len(res) == 0:
            logger.info(
                f"no memory for {user_id} in {timestamp_to_str(start_ts)} - {timestamp_to_str(end_ts)}"
            )
            return

        cls.summarize_context_with_saving(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            prompt=prompt.format(context=Memory.format_list(res)),
            memory_type=new_type,
        )

    @classmethod
    def generate_context_summary_with_one_minute(
        cls, user_id, start_ts: int, end_ts: int
    ):
        res = VisualContext.get_contexts_by_duration(
            user_id=user_id, start=start_ts, end=end_ts, limit=10
        )

        if len(res) == 0:
            logger.info(
                f"no context for {user_id} in {timestamp_to_str(start_ts)} - {timestamp_to_str(end_ts)}"
            )
            return

        cls.summarize_context_with_saving(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            prompt=CONTEXT_MEMORY_PROMPT.format(
                context=VisualContext.format_list(res, absolute_time=True)
            ),
            memory_type=MemoryType.ONE_MINUTE,
        )

    @classmethod
    def generate_context_summary_with_ten_minutes(
        cls, user_id, start_ts: int, end_ts: int
    ):
        return cls.generate_context_summary(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            old_type=MemoryType.ONE_MINUTE,
            new_type=MemoryType.TEN_MINUTES,
            prompt=CONTEXT_MEMORY_PROMPT,
            limit=10,
        )

    @classmethod
    def generate_context_summary_with_one_hour(
        cls, user_id, start_ts: int, end_ts: int
    ):
        return cls.generate_context_summary(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            old_type=MemoryType.TEN_MINUTES,
            new_type=MemoryType.ONE_HOUR,
            prompt=CONTEXT_MEMORY_PROMPT,
            limit=10,
        )

    @classmethod
    def generate_context_summary_with_three_hours(
        cls, user_id, start_ts: int, end_ts: int
    ):
        return cls.generate_context_summary(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            old_type=MemoryType.ONE_HOUR,
            new_type=MemoryType.THREE_HOURS,
            prompt=CONTEXT_MEMORY_PROMPT,
            limit=10,
        )

    @classmethod
    def generate_context_summary_with_one_day(cls, user_id, start_ts: int, end_ts: int):
        return cls.generate_context_summary(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            old_type=MemoryType.THREE_HOURS,
            new_type=MemoryType.ONE_DAY,
            prompt=CONTEXT_MEMORY_PROMPT,
            limit=10,
        )

    def _generate_memory(
        self, user_id: str, memory_type: MemoryType, delay=5 * 60 * 1000
    ):
        duration = get_duration(memory_type)

        for start_ts in range(self.start_date, self.end_date, duration):
            if start_ts >= get_timestamp() - duration - delay:
                continue

            end_ts = start_ts + duration
            res = Memory.get_memory_by_duration(
                self.user_id, memory_type, start_ts, end_ts, limit=1
            )

            if len(res) > 0:
                logger.info(
                    f"_generate_memory already finished for {user_id} in {timestamp_to_str(start_ts)} - {timestamp_to_str(end_ts)}, {res[-1]}"
                )
                continue

            logger.info(
                f"_generate_memory for {user_id} in {timestamp_to_str(start_ts)} - {timestamp_to_str(end_ts)}"
            )

            if memory_type == MemoryType.ONE_MINUTE:
                self.generate_context_summary_with_one_minute(user_id, start_ts, end_ts)
            elif memory_type == MemoryType.TEN_MINUTES:
                self.generate_context_summary_with_ten_minutes(
                    user_id, start_ts, end_ts
                )
            elif memory_type == MemoryType.ONE_HOUR:
                self.generate_context_summary_with_one_hour(user_id, start_ts, end_ts)
            elif memory_type == MemoryType.THREE_HOURS:
                self.generate_context_summary_with_three_hours(
                    user_id, start_ts, end_ts
                )
            elif memory_type == MemoryType.ONE_DAY:
                self.generate_context_summary_with_one_day(user_id, start_ts, end_ts)
            else:
                raise Exception(f"_generate_memory {memory_type} not implemented")

    def generate_memory(self):
        self._generate_memory(user_id=self.user_id, memory_type=MemoryType.ONE_MINUTE)
        self._generate_memory(user_id=self.user_id, memory_type=MemoryType.TEN_MINUTES)
        self._generate_memory(user_id=self.user_id, memory_type=MemoryType.ONE_HOUR)
        self._generate_memory(user_id=self.user_id, memory_type=MemoryType.THREE_HOURS)
        self._generate_memory(user_id=self.user_id, memory_type=MemoryType.ONE_DAY)


class MemoryGeneratorForContextWithCluster(MemoryGenerator):
    def __init__(self, user_id: str, start_date: int, end_date: int):
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    @staticmethod
    def summarize_context(user_id: str, prompt: str):
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0,
                pl_tags=[
                    "context-memorizer",
                    user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )
        res = chat_model.predict_with_prompt(prompt=prompt)
        return json.loads(res)

    @classmethod
    def summarize_context_with_saving(
        cls,
        user_id: str,
        start_ts: int,
        end_ts: int,
        prompt: str,
        memory_type: MemoryType,
        include_importance: bool = False,
        include_index: bool = False,
        save_to_vectordb: bool = False,
    ):
        res = cls.summarize_context(
            user_id=user_id,
            prompt=prompt,
        )

        memories = []
        if isinstance(res, dict):
            memories.append(
                Memory(
                    current_time=get_timestamp(),
                    memory_type=memory_type.value,
                    start_time=start_ts,
                    end_time=end_ts,
                    user_id=user_id,
                    content=res.get("summary", ""),
                    detail=res.get("detail", ""),
                )
            )

        elif isinstance(res, list):
            for item in res:
                memories.append(
                    Memory(
                        current_time=get_timestamp(),
                        memory_type=memory_type.value,
                        start_time=start_ts,
                        end_time=end_ts,
                        user_id=user_id,
                        content=item.get("summary", ""),
                        detail=item.get("detail", ""),
                    )
                )

        for memory in memories:
            if include_importance:
                memory.metadata["importance"] = MemoryEvaluatorWithEmotion(
                    user_id
                ).generate_importance(memory)
                memory.importance = (
                    memory.metadata["importance"]["emotional_arousal"] / 10
                )
            if include_index:
                memory.metadata["index"] = MemoryEvaluatorWithIndex(
                    user_id
                ).generate_index(memory)
            memory.save_memory()
            if save_to_vectordb:
                cls.save_to_vectordb(memory)
                if memory.memory_type == MemoryType.ONE_DAY.value:
                    # 添加到associative memory
                    memory.memory_type = MemoryType.ASSOCIATIVE_MEMORY.value
                    memory.save_memory_to_vectordb(check_exists=False)

        logger.info(
            f"generate context memory for {user_id} in {timestamp_to_str(start_ts)} - {timestamp_to_str(end_ts)}: {res}"
        )

    @classmethod
    def filter_unimportant_details(cls, memories: List[dict]):
        # filter details of unimportant events
        res = []
        for memory in memories:
            if (
                "metadata" in memory
                and "importance" in memory["metadata"]
                and "emotional_arousal" in memory["metadata"]["importance"]
                and memory["metadata"]["importance"]["emotional_arousal"] <= 5
            ):
                memory["detail"] = None
            res.append(memory)
        return res

    @classmethod
    def save_to_vectordb(cls, memory: Memory):
        if "index" not in memory.metadata or "importance" not in memory.metadata:
            return

        if memory.metadata["importance"]["emotional_arousal"] < 5:
            return

        for key, values in memory.metadata["index"].items():
            for value in values:
                memory.save_memory_to_vectordb_with_index(index=value)
                logger.info(
                    f"save memory to vectordb with index [{value}] for {memory}"
                )

    @classmethod
    def generate_context_summary(
        cls,
        user_id: str,
        start_ts: int,
        end_ts: int,
        old_type: MemoryType,
        new_type: MemoryType,
        prompt: PromptTemplate,
        limit: int = 0,
        similarity_threshold=0.85,
        include_importance: bool = False,
        include_index: bool = False,
        save_to_vectordb: bool = False,
    ):
        res = Memory.get_memory_by_duration(
            memory_type=old_type,
            user_id=user_id,
            start=start_ts,
            end=end_ts,
            limit=limit,
        )

        if len(res) == 0:
            logger.info(
                f"no memory for {user_id} in {timestamp_to_str(start_ts)} - {timestamp_to_str(end_ts)}"
            )
            return

        memorizes = [Memory.parse_obj(item) for item in res]
        cluster_list = text_cluster(
            [memory.content for memory in memorizes],
            similarity_threshold=similarity_threshold,
        )
        for cluster in cluster_list:
            cluster_res = res[cluster[0] : cluster[1]]
            if len(cluster_res) == 0:
                continue

            cls.summarize_context_with_saving(
                user_id=user_id,
                start_ts=memorizes[cluster[0] : cluster[1]][0].start_time,
                end_ts=memorizes[cluster[0] : cluster[1]][-1].end_time,
                prompt=prompt.format(
                    context=Memory.format_event_list(
                        cls.filter_unimportant_details(cluster_res)
                    )
                ),
                memory_type=new_type,
                include_importance=include_importance,
                include_index=include_index,
                save_to_vectordb=save_to_vectordb,
            )

    @classmethod
    def generate_context_summary_with_one_minute(
        cls, user_id, start_ts: int, end_ts: int
    ):
        res = VisualContext.get_contexts_by_duration(
            user_id=user_id, start=start_ts, end=end_ts, limit=10
        )

        if len(res) == 0:
            logger.info(
                f"no context for {user_id} in {timestamp_to_str(start_ts)} - {timestamp_to_str(end_ts)}"
            )
            return

        cls.summarize_context_with_saving(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            prompt=CONTEXT_EVENT_SUMMARY_PROMPT.format(
                context=VisualContext.format_list(res, absolute_time=True)
            ),
            memory_type=MemoryType.ONE_MINUTE,
            include_importance=True,
        )

    @classmethod
    def generate_context_summary_with_ten_minutes(
        cls, user_id, start_ts: int, end_ts: int
    ):
        return cls.generate_context_summary(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            old_type=MemoryType.ONE_MINUTE,
            new_type=MemoryType.TEN_MINUTES,
            prompt=CONTEXT_EVENT_PROMPT,
            similarity_threshold=0.80,
        )

    @classmethod
    def generate_context_summary_with_one_hour(
        cls, user_id, start_ts: int, end_ts: int
    ):
        return cls.generate_context_summary(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            old_type=MemoryType.TEN_MINUTES,
            new_type=MemoryType.ONE_HOUR,
            prompt=CONTEXT_EVENT_PROMPT,
            similarity_threshold=0.85,
        )

    @classmethod
    def generate_context_summary_with_three_hours(
        cls, user_id, start_ts: int, end_ts: int
    ):
        return cls.generate_context_summary(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            old_type=MemoryType.ONE_HOUR,
            new_type=MemoryType.THREE_HOURS,
            prompt=CONTEXT_EVENT_PROMPT,
            similarity_threshold=0.85,
        )

    @classmethod
    def generate_context_summary_with_one_day(cls, user_id, start_ts: int, end_ts: int):
        return cls.generate_context_summary(
            user_id=user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            old_type=MemoryType.THREE_HOURS,
            new_type=MemoryType.ONE_DAY,
            prompt=CONTEXT_EVENT_PROMPT,
            similarity_threshold=0.85,
            include_importance=True,
            include_index=True,
            save_to_vectordb=True,
        )

    def _generate_memory(
        self, user_id: str, memory_type: MemoryType, delay=5 * 60 * 1000
    ):
        duration = get_duration(memory_type)
        next_start_date = self.start_date

        first_context = VisualContext.get_contexts_by_duration(
            user_id=user_id, start=self.start_date, end=self.end_date, limit=1, sort=1
        )

        if len(first_context) == 0:
            logger.info(
                f"no context for {user_id} in {timestamp_to_str(self.start_date)} - {timestamp_to_str(self.end_date)}, skip"
            )
            return

        res = Memory.get_memory_by_duration(
            self.user_id, memory_type, next_start_date, self.end_date, limit=1
        )

        if len(res) > 0:
            next_start_date = res[0]["end_time"]

        for start_ts in range(next_start_date, self.end_date, duration):
            if start_ts >= self.end_date - duration - delay:
                continue
            end_ts = start_ts + duration
            try:
                if memory_type == MemoryType.ONE_MINUTE:
                    self.generate_context_summary_with_one_minute(
                        user_id, start_ts, end_ts
                    )
                elif memory_type == MemoryType.TEN_MINUTES:
                    self.generate_context_summary_with_ten_minutes(
                        user_id, start_ts, end_ts
                    )
                elif memory_type == MemoryType.ONE_HOUR:
                    self.generate_context_summary_with_one_hour(
                        user_id, start_ts, end_ts
                    )
                elif memory_type == MemoryType.THREE_HOURS:
                    self.generate_context_summary_with_three_hours(
                        user_id, start_ts, end_ts
                    )
                elif memory_type == MemoryType.ONE_DAY:
                    self.generate_context_summary_with_one_day(
                        user_id, start_ts, end_ts
                    )
                else:
                    return

                logger.info(
                    f"_generate_memory for {user_id} in {timestamp_to_str(start_ts)} - {timestamp_to_str(end_ts)}"
                )
            except Exception as e:
                logger.error(
                    f"error in _generate_memory for {user_id} in {timestamp_to_str(start_ts)} - {timestamp_to_str(end_ts)}:\n{traceback.format_exc()}"
                )

    def generate_memory(self):
        self._generate_memory(user_id=self.user_id, memory_type=MemoryType.ONE_MINUTE)
        self._generate_memory(user_id=self.user_id, memory_type=MemoryType.TEN_MINUTES)
        self._generate_memory(user_id=self.user_id, memory_type=MemoryType.ONE_HOUR)
        self._generate_memory(user_id=self.user_id, memory_type=MemoryType.THREE_HOURS)
        self._generate_memory(user_id=self.user_id, memory_type=MemoryType.ONE_DAY)


if __name__ == "__main__":
    # start_date = "2023-05-13 00:00:00"
    # end_date = "2023-05-14 00:00:00"
    user_id = "new-mem"
    start_date = "2023-05-19 00:00:00"
    end_date = "2023-05-20 00:00:00"
    start_date_ts = str_to_timestamp(start_date)
    end_date_ts = str_to_timestamp(end_date)

    MemoryGeneratorForContextWithCluster(
        user_id=user_id, start_date=start_date_ts, end_date=end_date_ts
    ).generate_memory()

    # res = Memory.get_memory_by_duration(
    #     user_id, MemoryType.ONE_MINUTE, start_date_ts, end_date_ts, limit=0
    # )
    # print(res)
    # memories = [Memory.parse_obj(item).content for item in res]
    # print(memories)
    # print(len(memories))
    #
    # cluster_list = text_cluster(memories, similarity_threshold=0.85)
    # for cluster in cluster_list:
    #     print(memories[cluster[0] : cluster[1]])
    #     print("\n")

    # print(Memory.format_event_list(res))
    # print("\n")

    # res = Memory.get_memory_by_duration(
    #     user_id, MemoryType.ONE_MINUTE, start_date_ts, end_date_ts, limit=0
    # )
    # # print(Memory.format_event_list(res))
    # print(res)
    # print("\n")

    # with open("test.txt", "w") as f:
    #     f.write(Memory.format_event_list(res))

    # res = Memory.get_memory_by_duration(
    #     user_id, MemoryType.TEN_MINUTES, start_date_ts, end_date_ts, limit=0
    # )
    # print(Memory.format_event_list(res))
    # print("\n")

    # res = Memory.get_memory_by_duration(
    #     user_id, MemoryType.ONE_HOUR, start_date_ts, end_date_ts, limit=0
    # )
    # print(Memory.format_event_list(res))
    # print("\n")
    #
    # res = Memory.get_memory_by_duration(
    #     user_id, MemoryType.THREE_HOURS, start_date_ts, end_date_ts, limit=0
    # )
    # print(Memory.format_event_list(res))
    # print("\n")

    res = Memory.get_memory_by_duration(
        user_id, MemoryType.ONE_DAY, start_date_ts, end_date_ts, limit=0
    )
    print(res)
    print(len(res))
    # for item in res:
    #     memory = Memory.parse_obj(item)
    #     MemoryGeneratorForContextWithCluster.save_to_vectordb(memory)
    # # print(Memory.format_event_list(res))
    # print("\n")

    # res = Memory.get_memory_by_duration(
    #     user_id, MemoryType.CONVERSATION, start_date_ts, end_date_ts, limit=0
    # )
    # print(Memory.format_list(res))
    # print("\n")
    # with open("conversation.txt", "w") as f:
    #     f.write(Memory.format_list(res))

    # # 按1分钟生成
    # duration = 60 * 1000
    # for start_ts in range(start_date_ts, end_date_ts, duration):
    #     end_ts = start_ts + duration
    #     MemoryGeneratorForContext.generate_context_summary_with_one_minute(
    #         user_id=user_id, start_ts=start_ts, end_ts=end_ts
    #     )
    #
    # # 按10分钟生成
    # duration = 10 * 60 * 1000
    # for start_ts in range(start_date_ts, end_date_ts, duration):
    #     end_ts = start_ts + duration
    #     MemoryGeneratorForContext.generate_context_summary_with_ten_minutes(
    #         user_id=user_id, start_ts=start_ts, end_ts=end_ts
    #     )
    #
    # # 按1小时生成
    # duration = 60 * 60 * 1000
    # for start_ts in range(start_date_ts, end_date_ts, duration):
    #     end_ts = start_ts + duration
    #     MemoryGeneratorForContext.generate_context_summary_with_one_hour(
    #         user_id=user_id, start_ts=start_ts, end_ts=end_ts
    #     )
    #
    # # 按3小时生成
    # duration = 3 * 60 * 60 * 1000
    # for start_ts in range(start_date_ts, end_date_ts, duration):
    #     end_ts = start_ts + duration
    #     MemoryGeneratorForContext.generate_context_summary_with_three_hours(
    #         user_id=user_id, start_ts=start_ts, end_ts=end_ts
    #     )
    #
    # # 按1天生成
    # duration = 24 * 60 * 60 * 1000
    # for start_ts in range(start_date_ts, end_date_ts, duration):
    #     end_ts = start_ts + duration
    #     MemoryGeneratorForContext.generate_context_summary_with_one_day(
    #         user_id=user_id, start_ts=start_ts, end_ts=end_ts
    #     )

    # res = Memory.query_memory_from_vectordb(
    #     user_id="hyln-memory", memory_types=[MemoryType.ONE_MINUTE], query="eating"
    # )
    # print(res)

    # MemoryGeneratorForContext.generate_context_summary_with_minutes(
    #     user_id="hyln-memory", start_ts=1683682920000, end_ts=1683682980000
    # )

    # MemoryGeneratorForContext.generate_context_summary_with_ten_minutes(
    #     user_id="hyln-memory", start_ts=1683693000000, end_ts=1683693600000
    # )

    # memory = Memory(
    #     current_time=get_timestamp(),
    #     memory_type=MemoryType.ONE_MINUTE.value,
    #     start_time=1683682920000,
    #     end_time=1683682980000,
    #     user_id="test",
    #     content="test",
    # )
    # print(memory.dict())
    # memory.save_memory()

    # prompt = """
    # """
    #
    # print(
    #     MemoryGeneratorForContext.summarize_context(
    #         user_id="hyln-memory", prompt=prompt
    #     )
    # )

    # from concurrent.futures import ThreadPoolExecutor
    # from tools.bs64 import bs642bytes
    # from tools.llava_api import LlavaVisualAssistant
    # from PIL import Image
    # import io
    #
    # duration = get_duration(MemoryType.ONE_MINUTE)
    # for start_ts in range(start_date_ts, end_date_ts, duration):
    #     end_ts = start_ts + duration
    #     res = VisualContext.get_contexts_by_duration(
    #         user_id=user_id, start=start_ts, end=end_ts, limit=0
    #     )
    #     if len(res) == 0:
    #         continue
    #
    #     for item in res:
    #         context = VisualContext.parse_obj(item)
    #         context.user_id = "new-mem"
    #         pool = ThreadPoolExecutor(max_workers=2)
    #
    #         scene_task = pool.submit(
    #             LlavaVisualAssistant.inference,
    #             Image.open(io.BytesIO(bs642bytes(context.original_image))),
    #         )
    #
    #         context.attention = pool.submit(
    #             LlavaVisualAssistant.inference,
    #             Image.open(io.BytesIO(bs642bytes(context.attended_image))),
    #         ).result()
    #         context.scene = scene_task.result()
    #         context.save_context()
    #         print(context.scene)
    #         print(context.attention)
    #         print("\n")
