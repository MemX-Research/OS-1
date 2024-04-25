import datetime
import json
import time

from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
)

from base.conversation import Conversation
from base.history import History
from base.history import HumanProfile, AIProfile
from base.prompt import Context
from templates.history import (
    REFLECTION_SYSTEM_PROMPT,
    REFLECTION_INPUT_PROMPT,
    PROFILE_SYSTEM_PROMPT,
)
from tools.helper import TextHelper
from tools.llm import ChatModel
from tools.log import logger
from tools.openai_api import get_openai_chatgpt
from tools.time_fmt import get_timestamp


class HistoryGeneratorWithSummary:
    def __init__(self, user_id: str):
        self.user_id = user_id

    @staticmethod
    def summarize_history(context: Context):
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.5,
                pl_tags=[
                    "chatgpt-history",
                    context.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        system_prompt = SystemMessagePromptTemplate.from_template(
            REFLECTION_SYSTEM_PROMPT.format(
                context_summary=context.context_summary,
                conversation_summary=context.conversation_summary,
                context=context.current_context,
            )
        )

        input_prompt = SystemMessagePromptTemplate.from_template(
            REFLECTION_INPUT_PROMPT.format()
        )

        chat_prompt = ChatPromptTemplate.from_messages(
            [system_prompt] + context.current_conversation + [input_prompt]
        )

        res = chat_model.predict_with_msgs(chat_prompt=chat_prompt)

        logger.info(f"generate history for {context.user_id}: {res}")

        return json.loads(res[0].text)

    def generate_history(self):
        context = Context(user_id=self.user_id, current_time=get_timestamp())
        context.get_latest_visual_context(seconds=300, limit=1)
        context.get_latest_conversation(seconds=300, limit=3)
        context.get_latest_history(seconds=604800, limit=1)

        if context.context_id is None or len(context.current_conversation) == 0:
            logger.info(f"{self.user_id}, context or conversation is empty")
            return

        res = self.summarize_history(context)

        history = History(
            current_time=context.current_time,
            user_id=context.user_id,
            human_personality=res["user_profile"],
            human_requirement=res["user_need"],
            context_summary=res["context_summary"],
            conversation_summary=res["conversation_summary"],
        )
        history.save_history()
        logger.info(f"{self.user_id}, save_history: {history.dict()}")


class ProfileHistoryGenerator:
    def __init__(self, user_id: str):
        self.user_id = user_id

    @classmethod
    def summarize_profile(cls, context: Context) -> dict:
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.5,
                pl_tags=[
                    "chatgpt-user-profile",
                    context.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        profile_json = cls.get_profile_json(context)
        profile_example_json = cls.get_profile_json()

        conversation_str = Conversation.msgs_to_string(
            context.current_conversation, ai_prefix="I"
        )

        system_prompt = PROFILE_SYSTEM_PROMPT.format(
            current_context=context.current_context,
            profile=profile_json,
            conversation=conversation_str,
            profile_example=profile_example_json,
        )

        res = chat_model.predict_with_prompt(prompt=system_prompt)

        res_obj = TextHelper.parse_json(res)
        res_obj = cls.post_process(res_obj)

        logger.info(f"generate profile for {context.user_id}: {res_obj}")

        return res_obj

    def generate_history(self, context=None):
        if not context:
            context = Context(
                user_id=self.user_id,
                current_time=get_timestamp(),
            )
            context.get_latest_visual_context(seconds=1800, limit=1)
            context.get_latest_conversation(seconds=1800, limit=1)
            context.get_latest_history(seconds=604800, limit=1)

        if context.context_id is None and len(context.current_conversation) == 0:
            logger.warning(f"{self.user_id}, No context and conversation")
            return

        res = self.summarize_profile(context)

        human_profile = HumanProfile.parse_obj(res["Human"])
        ai_profile = AIProfile.parse_obj(res["I"])

        new_history = History(
            current_time=context.current_time,
            user_id=context.user_id,
            human_profile=human_profile,
            ai_profile=ai_profile,
        )

        new_history.save_history()
        logger.info(f"{self.user_id}, save_history: {new_history.dict()}")

    @classmethod
    def post_process(cls, res_obj: dict):
        for user in res_obj:
            for key in res_obj[user]:
                if type(res_obj[user][key]) is list:
                    res_obj[user][key] = ", ".join(res_obj[user][key])
        return res_obj

    @classmethod
    def get_profile_json(cls, context: Context = None):
        if context:
            profile = {"Human": context.human_profile, "I": context.ai_profile}
        else:
            profile = {"Human": HumanProfile().dict(), "I": AIProfile().dict()}
        profile_json = json.dumps(profile, ensure_ascii=False, indent=4)
        profile_json = profile_json.replace(r"{", r"{{").replace(r"}", r"}}")
        return profile_json


if __name__ == "__main__":
    start = time.time()
    context = Context()
    context.context_id = "123"
    context.current_time = int(round(time.time() * 1000))
    context.user_id = "test"

    context.context_summary = "The human is at a carnival and looking at a claw machine filled with colorful toys."
    context.conversation_summary = "The human comments on how cute the claw machine is and Samantha encourages them to try it."
    context.current_context = "I sit in front of the computer"
    context.human_profile = HumanProfile().dict()
    context.ai_profile = AIProfile().dict()

    context.current_conversation = [
        HumanMessagePromptTemplate.from_template(
            "你好啊", additional_kwargs={"name": "Friend"}
        ),
        AIMessagePromptTemplate.from_template(
            "我是Samantha, 很高兴认识你", additional_kwargs={"name": "Samantha"}
        ),
        HumanMessagePromptTemplate.from_template(
            "你喜欢吃什么", additional_kwargs={"name": "Friend"}
        ),
        AIMessagePromptTemplate.from_template(
            "我喜欢吃菠萝", additional_kwargs={"name": "Samantha"}
        ),
    ]

    response = ProfileHistoryGenerator(user_id="test").generate_history(context)
    print(response)
    print("time: ", time.time() - start)

    # start = time.time()
    # response = Response()
    # context = Context()
    # context.current_time = int(round(time.time() * 1000))
    # context.user_id = "test"
    # context.user_text = "it is so beautiful."
    # context.location = "a garden"
    # context.object = "The lotus flower is in the middle of the lotus leaves"
    # context.people = "There is no one."
    # context.scene = "a field of lotus plants with a pink flower"
    # context.attention = "a lot of green lilies with pink flowers"
    # context.activity = "pausing to listen to the sounds of nature"
    # context.intention = "connecting with the environment"
    # context.emotion = "tranquil and peaceful"
    # response.context = context
    # response.reply = "Yes, it is. The colors of the lotus and lilies are so vibrant, and the sounds of nature are so calming. It's a great place to relax and connect with the environment."
    # response = HistoryGenerator().generate_history(response)
    # print(response)
    # print("time: ", time.time() - start)
