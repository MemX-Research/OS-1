import datetime
import json
from typing import List

import pymongo
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
)

from base.conversation import Conversation
from base.memorizer import Memory, MemoryType
from base.memorizer import MemoryGenerator
from base.visual import VisualContext
from templates.conversation import (
    CONVERSATION_SUMMARY_SYSTEM_PROMPT,
    CONVERSATION_SUMMARY_SYSTEM_INSTRUCTION,
    CONVERSATION_SUMMARY_FORMAT_PROMPT,
    CONVERSATION_SUMMARY_WITH_EVALUATION_PROMPT,
    USER_PERSONA_FROM_CONVERSATION_PROMPT,
)
from tools.helper import TextHelper
from tools.llm import ChatModel
from tools.log import logger
from tools.openai_api import get_openai_chatgpt
from tools.time_fmt import get_timestamp, get_past_timestamp
from tools.time_fmt import timestamp_to_str


class MemoryGeneratorForConversation(MemoryGenerator):
    minute_interval = 10  # 2段对话之间的最小间隔
    max_round = 10  # 多少轮对话之后，开始生成对话总结
    keep_round = 2  # 保留多少轮对话

    def __init__(
        self,
        user_id: str,
        start_time: int = get_past_timestamp(),
        current_time: int = get_timestamp(),
        minute_interval=10,
        max_round=10,
        keep_round=2,
    ) -> None:
        self.user_id = user_id
        self.start_time = start_time
        self.current_time = current_time
        self.minute_interval = minute_interval
        self.max_round = max_round
        self.keep_round = keep_round

    @staticmethod
    def summarize_conversation(user_id, chat_log):
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.5,
                pl_tags=[
                    "conversation-summary",
                    user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        chat_msgs = Conversation.format_list(chat_log)
        system_prompt = SystemMessagePromptTemplate.from_template(
            CONVERSATION_SUMMARY_SYSTEM_INSTRUCTION
        )
        format_prompt = SystemMessagePromptTemplate.from_template(
            CONVERSATION_SUMMARY_FORMAT_PROMPT
        )
        chat_prompt = ChatPromptTemplate.from_messages(
            [system_prompt] + chat_msgs + [format_prompt]
        )

        res = chat_model.predict_with_msgs(chat_prompt=chat_prompt)

        return json.loads(res[0].text)["summary"]

    def summarize_conversation_with_previous(self, user_id, previous_summary, chat_log):
        """deprecated"""
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.5,
                pl_tags=[
                    "conversation-summary",
                    user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )
        new_lines = ""

        for item in chat_log:
            if item["human"] != "":
                new_lines += f"Human: {item['human']}\n"
            if item["ai"] != "":
                new_lines += f"I: {item['ai']}\n"
        system_prompt = SystemMessagePromptTemplate.from_template(
            CONVERSATION_SUMMARY_SYSTEM_PROMPT.format(
                summary=previous_summary, new_lines=new_lines
            )
        )
        chat_prompt = ChatPromptTemplate.from_messages([system_prompt])

        res = chat_model.predict_with_msgs(chat_prompt=chat_prompt)

        return res[0].text

    def _get_chatlogs_to_summarize(
        self,
        user_id,
        start_time: int = get_past_timestamp(),
        current_time=get_timestamp(),
        memory_type=MemoryType.CONVERSATION,
    ):
        # 执行条件：超过时间间隔 或 当前对话超过最大轮数
        res = Memory.get_memory_by_duration(
            memory_type=memory_type,
            user_id=user_id,
            start=start_time,
            end=current_time,
            limit=1,
        )

        last_summary_time = start_time
        if len(res) != 0:
            last_summary_time = res[0]["end_time"]

        # get conversations since last summary
        # [{'human': 'Thank you.', 'ai': "No probs", "current_time": 123121}]
        conversations = Conversation.get_conversation_by_duration(
            user_id, last_summary_time + 1, current_time, limit=0
        )
        if len(conversations) == 0:
            logger.info(f"no conversation to summarize for {user_id}")
            return []

        chatlogs_to_summarize = []
        if (
            conversations[-1]["current_time"]
            < current_time - self.minute_interval * 60 * 1000
        ):
            # 超过时间间隔，总结所有
            chatlogs_to_summarize = conversations
        elif len(conversations) > self.max_round:
            # 超过最大轮数，保留{keep_round}轮，剩下的总结
            chatlogs_to_summarize = conversations[: -self.keep_round]
        else:
            # 不超过最大轮数，不需要总结
            logger.info(f"no conversation to summarize for {user_id}")

        return chatlogs_to_summarize

    def generate_conversation_summary(
        self,
        user_id,
        start_time: int = get_past_timestamp(),
        current_time=get_timestamp(),
    ):
        chatlogs_to_summarize = self._get_chatlogs_to_summarize(
            user_id, start_time, current_time
        )
        if len(chatlogs_to_summarize) == 0:
            return

        new_start_time = chatlogs_to_summarize[0]["current_time"]
        new_end_time = chatlogs_to_summarize[-1]["current_time"]
        logger.info(
            f"start generate conversation memory for {user_id} in {timestamp_to_str(new_start_time)} - {timestamp_to_str(new_end_time)}"
        )

        new_summary = self.summarize_conversation(user_id, chatlogs_to_summarize)

        Memory(
            current_time=get_timestamp(),
            memory_type=MemoryType.CONVERSATION.value,
            start_time=new_start_time,
            end_time=new_end_time,
            user_id=user_id,
            content=new_summary,
        ).save_memory()

        # memory = Memory(
        #     current_time=get_timestamp(),
        #     memory_type=MemoryType.CONVERSATION.value,
        #     start_time=new_start_time,
        #     end_time=new_end_time,
        #     user_id=user_id,
        #     content=new_summary,
        # )
        # memory.importance = MemoryEvaluator.generate_importance(memory) / 10
        # memory.save_memory()
        # memory.save_memory_to_vectordb()

        logger.info(
            f"generate conversation memory for {user_id} in {timestamp_to_str(new_start_time)} - {timestamp_to_str(new_end_time)}: {new_summary}"
        )

    def generate_memory(self):
        return self.generate_conversation_summary(
            self.user_id, start_time=self.start_time, current_time=self.current_time
        )

    def generate_conversation_summary_by_per(
        self, user_id, current_time=get_timestamp()
    ):
        """deprecated"""
        # 执行条件：超过时间间隔 或 当前对话超过最大轮数

        res = Memory.get_memory_by_duration(
            memory_type=MemoryType.CONVERSATION,
            user_id=user_id,
            start=0,
            end=current_time,
            limit=1,
        )
        res = list(
            Memory.find_memory(
                {
                    "user_id": user_id,
                    "memory_type": {
                        "$in": [
                            MemoryType.CONVERSATION.value,
                            MemoryType.CONVERSATION_UNFINISHED.value,
                        ],
                    },
                    "end_time": {
                        "$lte": current_time,
                    },
                },
                {
                    "_id": 0,
                },
            )
            .sort("current_time", pymongo.DESCENDING)
            .limit(1)
        )
        # 1. 没有记录/最后一条记录为已完成 => 当前为新对话
        # 2. 最后一条记录为未完成 => 当前为继续对话
        previous_summary = ""
        last_summary_time = 0
        new_start_time = 0
        if len(res) != 0:
            last_summary_time = res[0]["end_time"]
            if res[0]["memory_type"] == MemoryType.CONVERSATION_UNFINISHED.value:
                previous_summary = res[0]["content"]
                new_start_time = res[0]["start_time"]  # 继续之前的总结
        # get conversations since last summary
        # [{'human': 'Thank you.', 'ai': "No probs", "current_time": 123121}]
        conversations = Conversation.get_conversation_by_duration(
            user_id, last_summary_time + 1, current_time, limit=0
        )
        if len(conversations) == 0:
            logger.info(f"no conversation to summarize for {user_id}")
            return

        last_conversation_time = conversations[-1]["current_time"]
        if previous_summary == "":
            new_start_time = conversations[0]["current_time"]

        if last_conversation_time > current_time - self.minute_interval * 60 * 1000:
            # 未超过时间间隔
            if len(conversations) > self.max_round:
                # 超过最大轮数需要总结
                chatlogs_to_summarize = conversations[: -self.keep_round]
                new_end_time = conversations[-self.keep_round]["current_time"]
                memory_type = MemoryType.CONVERSATION_UNFINISHED.value
            else:
                # 不超过最大轮数，不需要总结
                logger.info(f"no conversation to summarize for {user_id}")
                return
        else:
            # 超过时间间隔，总结整个对话，标记当前对话结束
            chatlogs_to_summarize = conversations
            new_end_time = conversations[-1]["current_time"]
            memory_type = MemoryType.CONVERSATION.value

        new_summary = self.summarize_conversation_with_previous(
            user_id, previous_summary, chatlogs_to_summarize
        )

        Memory(
            current_time=get_timestamp(),
            memory_type=memory_type,
            start_time=new_start_time,
            end_time=new_end_time,
            user_id=user_id,
            content=new_summary,
        ).save_memory()

        logger.info(
            f"generate conversation memory for {user_id} in {timestamp_to_str(new_start_time)} - {timestamp_to_str(new_end_time)}: {new_summary}"
        )


class MemoryGeneratorForConversationWithEvaluation(MemoryGeneratorForConversation):
    def __init__(
        self,
        user_id: str,
        start_time: int = get_past_timestamp(),
        current_time: int = get_timestamp(),
        minute_interval=10,
        max_round=8,
        keep_round=2,
    ) -> None:
        super().__init__(
            user_id, start_time, current_time, minute_interval, max_round, keep_round
        )

    @staticmethod
    def summarize_conversation(user_id, chat_log: List[dict]) -> List[dict]:
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                max_tokens=2048,
                pl_tags=[
                    "conversation-summary-with-evaluation",
                    user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        conversation_str = Conversation.msgs_to_string(
            Conversation.format_list(chat_log), ai_prefix="I"
        )

        system_prompt = CONVERSATION_SUMMARY_WITH_EVALUATION_PROMPT.format(
            conversations=conversation_str,
        )
        item_list = []
        # retry 1 times
        tries = 0
        while tries < 2:
            tries += 1
            try:
                res = chat_model.predict_with_prompt(prompt=system_prompt)

                item_list = json.loads(res)
                break
            except Exception as e:
                logger.error(f"error in summarizing conversation: {e}")
                logger.warning("retry with gpt-3.5-turbo-16k")
                chat_model.llm.model_name = "gpt-3.5-turbo-16k"
                chat_model.llm.max_tokens = 4096
                continue

        return item_list

    @staticmethod
    def save_to_vectordb(memory: Memory):
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

        # 添加到associative memory
        memory.memory_type = MemoryType.ASSOCIATIVE_MEMORY.value
        memory.save_memory_to_vectordb(check_exists=False)

    def generate_conversation_summary(
        self,
        user_id,
        start_time: int = get_past_timestamp(),
        current_time=get_timestamp(),
    ) -> List:
        chatlogs_to_summarize = self._get_chatlogs_to_summarize(
            user_id, start_time, current_time
        )
        if len(chatlogs_to_summarize) == 0:
            return []

        new_start_time = chatlogs_to_summarize[0]["current_time"]
        new_end_time = chatlogs_to_summarize[-1]["current_time"]
        logger.info(
            f"start generate conversation memory for {user_id} in {timestamp_to_str(new_start_time)} - {timestamp_to_str(new_end_time)}"
        )

        item_list = self.summarize_conversation(user_id, chatlogs_to_summarize)
        new_mems = []
        item_num = len(item_list)
        time_interval = (new_end_time - new_start_time) / item_num
        for i, item in enumerate(item_list):
            metadata = {
                "importance": {
                    "emotion": item["friend_emotion"],
                    "emotional_arousal": item["emotional_arousal"],
                    "is_memorable": item["is_memorable"],
                },
                "index": {
                    "topic": item["topic"],
                },
            }
            # get location
            contexts = VisualContext.get_contexts_by_duration(
                self.user_id, start=new_start_time, end=new_end_time, limit=3
            )
            VisualContext.format_list(contexts)
            for context in contexts:
                context = VisualContext.parse_obj(context)
                if context.location:
                    metadata["index"]["location"] = [context.location]
                    break
            mem = Memory(
                current_time=get_timestamp(),
                memory_type=MemoryType.CONVERSATION.value,
                start_time=int(new_start_time + i * time_interval),
                end_time=int(new_start_time + (i + 1) * time_interval),
                user_id=user_id,
                content=item["summary"],
                metadata=metadata,
                importance=item["emotional_arousal"] / 10,
            )
            mem.save_memory()
            new_mems.append(mem)

        logger.info(
            f"generate {item_num} conversation memory for {user_id} in {timestamp_to_str(new_start_time)} - {timestamp_to_str(new_end_time)}"
        )
        return new_mems

    def _generate_conversation_memory(self, save_to_vectordb=True):
        new_mems = self.generate_conversation_summary(
            self.user_id, start_time=self.start_time, current_time=self.current_time
        )
        if save_to_vectordb:
            for mem in new_mems:
                self.save_to_vectordb(mem)

    @staticmethod
    def summarize_persona(user_id, chat_log: List[dict]) -> dict:
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                max_tokens=2048,
                pl_tags=[
                    "persona",
                    user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        conversation_str = Conversation.msgs_to_string(
            Conversation.format_list(chat_log), human_prefix="User1", ai_prefix="User2"
        )

        system_prompt = USER_PERSONA_FROM_CONVERSATION_PROMPT.format(
            conversations=conversation_str,
        )
        persona_obj = {}
        # retry 1 times
        tries = 0
        while tries < 2:
            tries += 1
            try:
                res = chat_model.predict_with_prompt(prompt=system_prompt)
                res = res.replace("User1", "User")
                persona_obj = TextHelper.parse_json(res)
                logger.info(persona_obj)
                break

            except Exception as e:
                logger.error(f"error in summarizing conversation: {e}")
                logger.warning("retry with gpt-3.5-turbo-16k")
                chat_model.llm.model_name = "gpt-3.5-turbo-16k"
                chat_model.llm.max_tokens = 4096
                continue

        return persona_obj

    def _generate_user_persona(self, save_to_vectordb=True, confidence_threshold=0.7):
        _chatlogs = self._get_chatlogs_to_summarize(
            self.user_id,
            self.start_time,
            self.current_time,
            memory_type=MemoryType.PERSONA,
        )
        # filter out "(No response)"
        chatlogs_to_summarize = []
        for chatlog in _chatlogs:
            if chatlog["human"].strip() != "(No response)":
                chatlogs_to_summarize.append(chatlog)
        if len(chatlogs_to_summarize) == 0:
            return

        new_start_time = chatlogs_to_summarize[0]["current_time"]
        new_end_time = chatlogs_to_summarize[-1]["current_time"]
        logger.info(
            f"start generate persona for {self.user_id} in {timestamp_to_str(new_start_time)} - {timestamp_to_str(new_end_time)}"
        )

        persona_obj = self.summarize_persona(self.user_id, chatlogs_to_summarize)
        new_personas = []

        for k, v in persona_obj.items():
            for item in v:
                splits = item.split(" - ")
                if len(splits) > 2:
                    logger.warning(f"invalid persona: {item}")
                    continue
                elif len(splits) == 1:
                    score = 1.0

                else:
                    content = splits[0]
                    score = float(splits[1])
                stop_words = [
                    "current",
                    "today",
                    "yesterday",
                    "tomorrow",
                    "unknown",
                    "not respond",
                    "have no",
                ]
                if any([w in content.lower() for w in stop_words]):
                    continue

                new_personas.append((content, k, score))

        for item in new_personas:
            mem = Memory(
                current_time=get_timestamp(),
                memory_type=MemoryType.PERSONA.value,
                start_time=new_start_time,
                end_time=new_end_time,
                user_id=self.user_id,
                content=item[0],
                importance=item[2],
                metadata={"type": item[1], "score": item[2]},
            )
            mem.save_memory()

            if save_to_vectordb:
                if item[2] >= confidence_threshold:
                    mem.save_memory_to_vectordb(check_exists=True)
                    # 添加到associative memory
                    mem.memory_type = MemoryType.ASSOCIATIVE_MEMORY.value
                    mem.save_memory_to_vectordb(check_exists=True)
        logger.info(
            f"generate {len(new_personas)} personas for {self.user_id} in {timestamp_to_str(new_start_time)} - {timestamp_to_str(new_end_time)}"
        )

    def generate_memory(self):
        self._generate_conversation_memory(save_to_vectordb=True)
        self._generate_user_persona(save_to_vectordb=True)


if __name__ == "__main__":
    # mem = MemoryGeneratorForConversation(user_id="test")
    mem = MemoryGeneratorForConversationWithEvaluation(user_id="test")

    mem.generate_conversation_summary("test")
