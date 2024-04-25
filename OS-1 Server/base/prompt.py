import datetime
import json
import re
import traceback
from abc import ABCMeta, abstractmethod
from typing import List
from typing import Optional

from bson import json_util
from langchain.prompts.chat import HumanMessagePromptTemplate

from base.conversation import Conversation
from base.history import History, HumanProfile, AIProfile
from base.memorizer import MemoryType, Memory
from base.tag import Tag
from base.visual import VisualContext
from templates.memory import MEMORY_QUERY_PROMPT, MEMORY_QUERY_PROMPT_LLAMA
from tools.llama_api import LlamaAPI
from tools.llm import ChatModel
from tools.log import logger
from tools.openai_api import get_openai_chatgpt
from tools.time_fmt import get_timestamp, get_past_timestamp


class Context(Tag):
    user_text: Optional[str] = None
    user_audio: Optional[str] = None

    human_profile: Optional[dict] = HumanProfile().dict()
    ai_profile: Optional[dict] = AIProfile().dict()

    context_memory: Optional[str] = None
    conversation_memory: Optional[str] = None
    unified_memory: Optional[str] = None
    persona_memory: Optional[str] = None

    context_summary: Optional[str] = None
    conversation_summary: Optional[str] = None

    current_context: Optional[str] = None
    current_conversation: Optional[List] = None

    context_id: Optional[str] = None
    history_id: Optional[str] = None

    policy_action: Optional[str] = None
    search_report: Optional[str] = None

    def update_current_context(self, res, absolute_time=False):
        if len(res) == 0:
            res = [{"current_time": self.current_time}]  # empty context
        else:
            self.context_id = str(res[-1]["_id"])
        self.current_context = VisualContext.format_list(
            res, absolute_time=absolute_time, now=self.current_time
        )

    def get_visual_context_by_duration(
        self, start: int, end: int, limit: int = 1, absolute_time=False
    ):
        res = VisualContext.get_contexts_by_duration(
            self.user_id, start=start, end=end, limit=limit
        )
        self.update_current_context(res, absolute_time=absolute_time)

    def get_latest_visual_context(self, seconds=1800, limit=1, absolute_time=False):
        res = VisualContext.get_latest_context(
            self.user_id, seconds=seconds, limit=limit, end=self.current_time
        )
        self.update_current_context(res, absolute_time=absolute_time)

    def update_current_conversation(self, res):
        chat_msgs = Conversation.format_list(res)
        if self.user_text:
            chat_msgs.append(HumanMessagePromptTemplate.from_template(self.user_text))
        self.current_conversation = chat_msgs

    def get_conversation_by_duration(self, start: int, end: int, limit: int = 3):
        res = Conversation.get_conversation_by_duration(
            self.user_id, start=start, end=end, limit=limit
        )
        self.update_current_conversation(res)

    def get_latest_conversation(self, seconds=1800, limit=3):
        res = Conversation.get_latest_conversation(
            self.user_id, seconds=seconds, limit=limit, end=self.current_time
        )
        self.update_current_conversation(res)

    def get_latest_history(self, seconds=604800, limit=1):
        res = History.get_latest_history(
            self.user_id, seconds=seconds, limit=limit, end=self.current_time
        )
        for item in res:
            self.history_id = str(item["_id"])
            history = History.parse_raw(json_util.dumps(item))
            self.human_profile = history.human_profile.dict(
                exclude_defaults=True, exclude_none=True
            )
            self.ai_profile = history.ai_profile.dict(
                exclude_defaults=True, exclude_none=True
            )

    def get_context_memory(self, k=3):
        if self.current_context is None or self.current_context == "":
            return
        docs = Memory.query_memory_from_vectordb(
            self.user_id,
            memory_types=[MemoryType.ONE_HOUR],
            query=self.current_context,
            k=k,
        )
        self.context_memory = Memory.format_memory_docs(docs)

    def get_conversation_memory(self, k=3):
        if self.current_context is None or self.current_context == "":
            return
        docs = Memory.query_memory_from_vectordb(
            self.user_id,
            memory_types=[MemoryType.CONVERSATION],
            query=self.current_context,
            k=k,
        )
        self.conversation_memory = Memory.format_memory_docs(docs)

    def _generate_queries(self):
        if self.current_conversation is None or len(self.current_conversation) == 0:
            logger.warning("No conversation, stop generating queries.")
            return []
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.2,
                max_tokens=512,
                pl_tags=[
                    "memory-query",
                    self.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )
        if self.current_conversation is None:
            self.current_conversation = []
        conversation_str = Conversation.msgs_to_string(
            self.current_conversation[-3:], ai_prefix="I"
        )

        system_prompt = MEMORY_QUERY_PROMPT.format(
            conversations=conversation_str,
            current_context=self.current_context,
        )

        res = chat_model.predict_with_prompt(prompt=system_prompt)
        try:
            queries = set()
            res = json.loads(res)
            keys = ["context_cues", "conversation_cues"]
            for key in keys:
                if key in res:
                    queries.update(res[key])
            queries = list(queries)
        except Exception as e:
            logger.error("generate_queries:", e)
            queries = []
        return queries

    def _generate_queries_with_llama(self):
        if self.current_conversation is None or len(self.current_conversation) == 0:
            logger.warning("No conversation, stop generating queries.")
            return []

        url = "http://localhost:8004"
        chat_model = LlamaAPI(url)
        if self.current_conversation is None:
            self.current_conversation = []
        conversation_str = Conversation.msgs_to_string(
            self.current_conversation[-3:], ai_prefix="I"
        ).strip()

        current_context = self.current_context
        if self.current_context is None or "did not noticing" in self.current_context:
            current_context = "NONE"
        system_prompt = MEMORY_QUERY_PROMPT_LLAMA.format(
            conversations=conversation_str,
            current_context=current_context,
        )

        try:
            res = chat_model.call_model(
                prompt=system_prompt, temperature=0.0, max_new_tokens=80, stop="<"
            )
            res = res["text"]
            queries = set()
            context_pat = re.compile(r"context:(.*)")
            conversation_pat = re.compile(r"conversation:(.*)")
            matched_context = context_pat.findall(res)

            tem_cues = []
            if len(matched_context) > 0:
                tem_cues.extend(matched_context[0].split(";"))

            matched_conversation = conversation_pat.findall(res)

            if len(matched_conversation) > 0:
                tem_cues.extend(matched_conversation[0].split(";"))

            for cue in tem_cues:
                cue = cue.strip()
                if cue != "":
                    queries.add(cue.strip())

            queries = list(queries)
        except Exception as e:
            logger.error("generate_queries:", e, traceback.format_exc())
            queries = []
        logger.info(
            f"vicuna prompt:\nConversation: {conversation_str}\nContext: {current_context}\nreturned index: {queries}"
        )
        return queries

    def get_unified_memory(self, k=3, score_threshold=0.8):
        queries = self._generate_queries_with_llama()

        res = Memory().query_memory_from_vectordb_by_indexes(
            self.user_id, queries, mem_k=k, score_threshold=score_threshold
        )
        self.unified_memory = Memory.format_memory_docs(res, now=self.current_time)

    def get_persona_memory(self, k=3, score_threshold=0.8):
        """Directly query persona memory with `user_text`."""
        if self.user_text is None or self.user_text == "(No response)":
            logger.warning("No user_text, stop query_persona_memory.")
            return
        docs = Memory().query_persona_from_vectordb(
            self.user_id, query=self.user_text, k=k, score_threshold=score_threshold
        )
        self.persona_memory = "\n".join([doc.page_content for doc in docs])

    def get_context_summary(self):
        res = Memory.get_memory_by_duration(
            self.user_id,
            memory_type=MemoryType.ONE_HOUR,
            start=get_past_timestamp(current_time=self.current_time),
            end=self.current_time,
            limit=10,
        )
        self.context_summary = Memory.format_list(
            res, absolute_time=False, now=self.current_time
        )
        if len(res) == 0:
            return None
        else:
            return res[-1]["end_time"]

    def get_conversation_summary(self):
        res = Memory.get_memory_by_duration(
            self.user_id,
            memory_type=MemoryType.CONVERSATION,
            start=get_past_timestamp(current_time=self.current_time),
            end=self.current_time,
            limit=5,
        )
        self.conversation_summary = Memory.format_list(
            res, absolute_time=False, now=self.current_time
        )
        if len(res) == 0:
            return None
        else:
            return res[-1]["end_time"]

    def get_current_context(
        self, start: int = None, seconds=1800, limit=1, absolute_time=False
    ):
        if start is None:
            return self.get_latest_visual_context(
                seconds=seconds, limit=limit, absolute_time=absolute_time
            )
        return self.get_visual_context_by_duration(
            start, self.current_time, limit=limit, absolute_time=absolute_time
        )

    def get_current_conversation(self, start: int = None, seconds=1800, limit=3):
        if start is None:
            return self.get_latest_conversation(seconds=seconds, limit=limit)
        return self.get_conversation_by_duration(start, get_timestamp(), limit=limit)


class PromptGenerator(metaclass=ABCMeta):
    @abstractmethod
    def generate_prompt(self, context: Context) -> Context:
        pass
