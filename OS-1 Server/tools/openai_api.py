import os
import random
from multiprocessing import Queue
from typing import Any, Union
import json

import promptlayer
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chat_models import PromptLayerChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.schema import LLMResult

from base.message import Message
from tools.embedding_api import CustomEmbeddings
from tools.helper import TextHelper
from tools.redis_client import RedisClientProxy, UserStatus
from tools.time_fmt import get_timestamp
from langchain.embeddings import HuggingFaceEmbeddings

promptlayer.api_key = os.getenv("PROMPTLAYER_API_KEY")
openai = promptlayer.openai

# 实际使用时,在系统中设置环境变量
openai_api_base_default = os.getenv("OPENAI_API_BASE_URL")
openai_api_keys = [os.getenv("OPENAI_API_KEY")]
gpt4_api_keys = [os.getenv("OPENAI_API_KEY")]
chat_models = ["gpt-3.5-turbo"]
gpt4_chat_models = ["gpt-4-turbo"]


def random_list(lst):
    return lst[random.randint(0, len(lst) - 1)]


def get_openai_api_key():
    return random_list(openai_api_keys)


def get_openai_chat_model():
    return random_list(chat_models)


def get_gpt4_api_key():
    return random_list(gpt4_api_keys)


def get_gpt4_chat_model():
    return random_list(gpt4_chat_models)


def get_openai_chatgpt(verbose=True, **kwargs):
    return PromptLayerChatOpenAI(
        verbose=verbose,
        openai_api_key=get_openai_api_key(),
        openai_api_base=openai_api_base_default,
        model_name=get_openai_chat_model(),
        **kwargs,
    )


def get_openai_gpt4(verbose=True, **kwargs):
    return PromptLayerChatOpenAI(
        verbose=verbose,
        model_name=get_gpt4_chat_model(),
        openai_api_key=get_gpt4_api_key(),
        openai_api_base=openai_api_base_default,
        **kwargs,
    )


def get_openai_embedding():
    return OpenAIEmbeddings(
        openai_api_key=get_openai_api_key(),
        openai_api_base=openai_api_base_default,
    )


def get_hf_embedding():
    return CustomEmbeddings()


EmbeddingModel = get_hf_embedding()


class UserInterrupt(Exception):
    def __init__(
        self,
        response=None,
        user_id=None,
    ):
        super(UserInterrupt, self).__init__(response)
        self.response = response
        self.user_id = user_id

    def __str__(self):
        return f"Interrupted by `{self.user_id}`: {self.response}"


class StreamingCallbackHandler(StreamingStdOutCallbackHandler):
    def __init__(self, queue: Queue, end_token: str = "$END$"):
        self.queue = queue
        self.end_token = end_token

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run on LLM end. Only available when streaming is enabled."""
        self.queue.put(self.end_token)

    def on_llm_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Run when LLM errors."""
        self.queue.put(self.end_token)

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run on new LLM token. Only available when streaming is enabled."""
        if token == "":
            return
        self.queue.put(token)


class StreamingCallbackHandlerWithRedis(StreamingStdOutCallbackHandler):
    def __init__(self, user_id: str, interruptable: bool = False):
        self.tokens = []
        self.user_id = user_id
        self.full_message = ""
        self.interruptable = interruptable
        self.emotion = ""
        self.emotion_flag = False
        self.token_count = 0
        self.start_time = get_timestamp()
        self.has_send_first_msg = False
        if interruptable:
            self.raise_error = True

    def send_message(self):
        if len(self.tokens) == 0:
            return
        msg = Message(
            start_time=self.start_time,
            current_time=get_timestamp(),
            user_id=self.user_id,
            text="".join(self.tokens),
            emotion=self.emotion,
        )

        # 第一个语音包包含统计信息
        if not self.has_send_first_msg:
            self.has_send_first_msg = True
            gpt_delay = msg.current_time - self.start_time
            RedisClientProxy.set_user_statistic(self.user_id, "gpt_delay", gpt_delay)

            msg.first_pkg = True
        RedisClientProxy.push_msg_text(msg.json())
        self.tokens = []

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run on LLM end. Only available when streaming is enabled."""
        self.send_message()

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run on new LLM token. Only available when streaming is enabled."""
        if self.interruptable:
            self.check_interrupt()  # raise UserInterrupt
        if token == "":
            return
        self.token_count += 1
        self.full_message += token

        if self.token_count == 1 and token[0] == "(":  # begin with emotion tokens
            self.emotion_flag = True
            self.emotion += token[0:]
            return
        if self.emotion_flag:
            if token in [")", ") "]:
                self.emotion_flag = False  # end of emotion tokens
                return
            self.emotion += token
            return

        self.tokens.append(token)

        if TextHelper.is_text(token):
            return
        self.send_message()

    def check_interrupt(self):
        status = RedisClientProxy.get_user_status(self.user_id)
        if status == UserStatus.INTERRUPT:
            RedisClientProxy.set_user_status(
                self.user_id, UserStatus.IDLE
            )  # reset status
            raise UserInterrupt(self.full_message, self.user_id)
        if status == UserStatus.OFF:
            raise UserInterrupt(self.full_message, self.user_id)
