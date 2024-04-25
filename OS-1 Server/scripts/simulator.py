from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from tools.helper import TextHelper
from tools.llm import ChatModel
from tools.openai_api import (
    get_openai_chatgpt,
)
from base.prompt import Context
from core.response import ResponseGeneratorWithGPT4

chatlogs = []
user_chatlogs = []


class ChatbotSimulator:
    @staticmethod
    def generate_response():
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=1.0,
                n=1,
            )
        )

        system_prompt = SystemMessagePromptTemplate.from_template(
            "You are chatting with me."
        )

        chat_prompt = ChatPromptTemplate.from_messages(
            [system_prompt]
            + chatlogs
            + [
                SystemMessagePromptTemplate.from_template(
                    "You should say a sentence to me."
                )
            ]
        )

        res = TextHelper.remove_non_text(
            chat_model.predict_with_msgs(chat_prompt)[0].text.split(":")[-1]
        )

        chatlogs.append(AIMessagePromptTemplate.from_template(res))
        print(f"Samantha: {chatlogs[-1].prompt.template}")
        with open("chatlogs.txt", "a") as f:
            f.write(f"Samantha: {chatlogs[-1].prompt.template}\n")


class SelfChatbotSimulator:
    @staticmethod
    def generate_response():
        res = (
            ResponseGeneratorWithGPT4()
            .generate_response(
                context=Context(user_id="self-chat", current_conversation=chatlogs)
            )
            .reply
        )

        chatlogs.append(
            AIMessagePromptTemplate.from_template(
                res, addtional_args={"user_name": "chatbot"}
            )
        )
        user_chatlogs.append(
            HumanMessagePromptTemplate.from_template(
                res, addtional_args={"user_name": "user"}
            )
        )
        print(f"Samantha: {chatlogs[-1].prompt.template}")
        with open("chatlogs.txt", "a") as f:
            f.write(f"Samantha: {chatlogs[-1].prompt.template}\n")


class UserSimulator:
    @staticmethod
    def generate_response():
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=1.0,
                n=1,
            )
        )

        system_prompt = SystemMessagePromptTemplate.from_template(
            # "Your name is Alex. You are chatting with Samantha. You can tell samantha directly what you don't like about her response."
            # "You are chatting with me. You are a graduate student busy doing research. You have a lot of trouble with your life. You are very sad. Do not say you are a language model."
            "You ate KFC tonight. Do not say you are a language model."
        )

        chat_prompt = ChatPromptTemplate.from_messages(
            [system_prompt]
            + user_chatlogs
            + [SystemMessagePromptTemplate.from_template("You should say a sentence.")]
        )

        res = TextHelper.remove_non_text(
            chat_model.predict_with_msgs(chat_prompt)[0].text.split(":")[-1]
        )

        chatlogs.append(
            HumanMessagePromptTemplate.from_template(
                res, addtional_args={"user_name": "user"}
            )
        )
        user_chatlogs.append(
            AIMessagePromptTemplate.from_template(
                res, addtional_args={"user_name": "chatbot"}
            )
        )
        print(f"User: {chatlogs[-1].prompt.template}")
        with open("chatlogs.txt", "a") as f:
            f.write(f"User: {chatlogs[-1].prompt.template}\n")


if __name__ == "__main__":
    import time

    start = time.time()

    for i in range(50):
        SelfChatbotSimulator.generate_response()
        UserSimulator.generate_response()
        time.sleep(10)

    print(time.time() - start)
