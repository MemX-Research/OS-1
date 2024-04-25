import datetime
import time

from langchain.callbacks.manager import CallbackManager
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from base.conversation import Conversation
from base.prompt import Context
from base.response import Response
from base.response import ResponseGenerator
from core.prompt import PromptGeneratorWithHistory
from templates.custom_prompt import CUSTOM_SYSTEM_PROMPT, DEFAULT_SYS_PROMPT
from templates.response import CHAT_SYSTEM_PROMPT_LLAMA
from tools.authorization import UserController
from tools.helper import TextHelper
from tools.llama_api import LlamaModel
from tools.llm import ChatModel
from tools.log import logger
from tools.openai_api import (
    StreamingCallbackHandlerWithRedis,
    UserInterrupt,
    get_openai_gpt4,
)
from tools.time_fmt import get_timestamp


class ResponseGeneratorWithGPT4(ResponseGenerator):
    def generate_response(self, context: Context) -> Response:
        chat_model = ChatModel(
            llm=get_openai_gpt4(
                temperature=1.0,
                streaming=True,
                n=1,
                pl_tags=[
                    "gpt4-chatbot",
                    context.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
                callback_manager=CallbackManager(
                    [
                        StreamingCallbackHandlerWithRedis(
                            user_id=context.user_id, interruptable=True
                        )
                    ]
                ),
            )
        )

        # custom system prompt
        user = UserController().get_user(context.user_id)
        user_prompt = DEFAULT_SYS_PROMPT
        if user:
            user_prompt = user.system_prompt

        system_prompt = SystemMessagePromptTemplate.from_template(
            CUSTOM_SYSTEM_PROMPT.format(
                user_prompt=user_prompt,
                human_profile="\n".join(
                    [
                        f"{key}: {value}"
                        for key, value in context.human_profile.items()
                        if value
                    ]
                ),
                # ai_profile="\n".join(
                #     [f"{key}: {value}" for key, value in context.ai_profile.items() if value]
                # ),
                # context_memory=context.context_memory,
                # conversation_memory=context.conversation_memory,
                unified_memory=context.unified_memory,
                persona_memory=context.persona_memory,
                # context_summary=context.context_summary,
                conversation_summary=context.conversation_summary,
                context=context.current_context,
                policy=context.policy_action,
                info=context.search_report,
            )
        )

        chat_prompt = ChatPromptTemplate.from_messages(
            [system_prompt] + context.current_conversation
        )

        try:
            res = chat_model.predict_with_msgs(chat_prompt)
            res = res[0].text
        except UserInterrupt as e:
            res = e.response + "..." + "(INTERRUPTED BY USER)"

        logger.info(f"gpt4 response for {context.user_id}: {res}")

        res = TextHelper.remove_non_text(res)

        return Response(context=context, prompt=chat_prompt.format(), reply=res)


class ResponseGeneratorWithLLama(ResponseGenerator):
    def generate_response(self, context: Context) -> Response:
        chat_model = ChatModel(
            llm=LlamaModel(
                temperature=0.5,
                url="http://localhost:8001",
                resp_prefix="(",
                streaming=True,
                callback_manager=CallbackManager(
                    [StreamingCallbackHandlerWithRedis(user_id=context.user_id)]
                ),
            )
        )

        system_prompt = SystemMessagePromptTemplate.from_template(
            CHAT_SYSTEM_PROMPT_LLAMA.format(
                human_profile="\n".join(
                    [
                        f"{key}: {value}"
                        for key, value in context.human_profile.items()
                        if value
                    ]
                ),
                ai_profile="\n".join(
                    [
                        f"{key}: {value}"
                        for key, value in context.ai_profile.items()
                        if value
                    ]
                ),
                unified_memory=context.unified_memory,
                persona_memory=context.persona_memory,
                context_summary=context.context_summary,
                conversation_summary=context.conversation_summary,
                context=context.current_context,
            )
        )

        chat_prompt = ChatPromptTemplate.from_messages(
            [system_prompt] + context.current_conversation
        )

        try:
            res = chat_model.predict_with_msgs(chat_prompt)
            res = res[0].text
        except UserInterrupt as e:
            res = e.response + "..." + "(INTERRUPTED BY USER)"

        logger.info(f"llama response for {context.user_id}: {res}")

        res = TextHelper.remove_non_text(res)

        return Response(context=context, prompt=chat_prompt.format(), reply=res)


if __name__ == "__main__":
    start = time.time()

    context = Context()
    context.user_id = "test1"
    context.current_time = get_timestamp()
    context.user_text = "Can you tell me a joke?"
    chat_msgs = []
    # chat_msgs.append(
    #     HumanMessagePromptTemplate.from_template(
    #         "你好啊", additional_kwargs={"name": "User"}
    #     )
    # )
    # chat_msgs.append(
    #     AIMessagePromptTemplate.from_template(
    #         "我是Samantha, 很高兴认识你", additional_kwargs={"name": "Samantha"}
    #     )
    # )
    chat_msgs.append(
        HumanMessagePromptTemplate.from_template(
            context.user_text, additional_kwargs={"name": "User"}
        )
    )
    context.current_conversation = chat_msgs
    context = PromptGeneratorWithHistory().generate_prompt(context)
    # print(context)
    res = ResponseGeneratorWithGPT4().generate_response(context)
    print(res)
    Conversation(
        current_time=res.context.current_time,
        user_id=res.context.user_id,
        human=res.context.user_text,
        ai=res.reply,
        context_id=res.context.context_id,
        history_id=res.context.history_id,
        audio=res.context.user_audio,
        prompt=res.prompt,
    ).save_conversation()
    print("time: ", time.time() - start)
