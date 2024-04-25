import datetime

from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from templates.agent import POLICY_PLANNER_PROMPT, POLICY_DECIDER_PROMPT
from tools.llm import ChatModel
from tools.log import logger
from tools.openai_api import get_openai_chatgpt


class PolicyPlaner:

    def __init__(self, user_id: str):
        self.user_id = user_id

    def generate(self, context: str, **kwargs):
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                pl_tags=[
                    "policy-planer",
                    self.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        user_msg = f"[Context]\n{context}"
        plan = kwargs.get("plan")
        if plan:
            user_msg += f"\n{plan}"

        chat_prompt = ChatPromptTemplate.from_messages(
            [SystemMessagePromptTemplate.from_template(POLICY_PLANNER_PROMPT),
             HumanMessagePromptTemplate.from_template(user_msg)]
        )

        res = chat_model.predict_with_msgs(chat_prompt)[0].text

        logger.info(f"generate policy plan for {self.user_id}: {res}")

        return res


class PolicyDecider:

    def __init__(self, user_id: str):
        self.user_id = user_id

    def generate(self, context: str, **kwargs):
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                pl_tags=[
                    "policy-decider",
                    self.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        user_msg = f"[Context]\n{context}"
        plan = kwargs.get("plan")
        if plan:
            user_msg += f"\n{plan}"

        chat_prompt = ChatPromptTemplate.from_messages(
            [SystemMessagePromptTemplate.from_template(POLICY_DECIDER_PROMPT),
             HumanMessagePromptTemplate.from_template(user_msg)]
        )

        res = chat_model.predict_with_msgs(chat_prompt)[0].text

        logger.info(f"generate policy decision for {self.user_id}: {res}")

        return res


if __name__ == "__main__":
    planer = PolicyPlaner(user_id="test")
    plan = planer.generate(
        context="User: I have doubts about my own abilities, and I feel confused about the path ahead.")
    print(plan)

    decider = PolicyDecider(user_id="test")
    decision = decider.generate(
        context="User: I have doubts about my own abilities, and I feel confused about the path ahead.", plan=plan)
    print(decision)
