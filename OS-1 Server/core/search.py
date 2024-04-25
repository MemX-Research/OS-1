import datetime
import re
import time
from multiprocessing import Manager
from threading import Thread
from typing import List

from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from base.memorizer import Memory
from templates.agent import SEARCH_PLANNER_PROMPT, SEARCH_REPORTER_PROMPT
from tools.llm import ChatModel
from tools.log import logger
from tools.openai_api import get_openai_chatgpt


def dict_to_list(docs: dict):
    tmp = {}
    for _, value in docs.items():
        for item in value:
            tmp[item] = None
    return [key for key, _ in tmp.items()]


def remove_duplicate_list(docs: List):
    tmp = {}
    res = []
    for item in docs:
        if item not in tmp:
            res.append(item)
        tmp[item] = None
    return res


class SearchPlaner:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def generate(self, context: str, **kwargs):
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                pl_tags=[
                    "search-planer",
                    self.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        user_msg = f"[Context]\n{context}"
        info = kwargs.get("info")
        if info:
            user_msg += f"\n[Info]\n{info}"
        plan = kwargs.get("plan")
        if plan:
            user_msg += f"\n{plan}"

        chat_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(SEARCH_PLANNER_PROMPT),
                HumanMessagePromptTemplate.from_template(user_msg),
            ]
        )

        res = chat_model.predict_with_msgs(chat_prompt)[0].text.replace("[Query]", "")
        res = re.sub(re.compile("""\d+\s*\.\s*"""), "", res)

        logger.info(f"generate search plan for {self.user_id}: {res}")

        return [item for item in res.split("\n") if item != ""]


class SearchWorker:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def search(
        self,
        queries: List[str],
        k=1,
        score_threshold=0.5,
    ) -> dict:

        start = time.time()
        docs = Manager().dict()

        def query_vectordb(query):
            doc = Memory().query_associative_memory_from_vectordb(
                user_id=self.user_id,
                query=query,
                k=k,
                score_threshold=score_threshold,
            )
            if len(doc) > 0:
                docs[query] = [item.page_content for item in doc]

        thread_list = []
        for query in queries:
            thread = Thread(
                target=query_vectordb,
                args=(query,),
            )
            thread.start()
            thread_list.append(thread)
        for thread in thread_list:
            thread.join()

        logger.info(f"search for {self.user_id} cost {time.time() - start}: {docs}")

        return docs


class SearchReporter:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def generate(self, context: str, **kwargs):
        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                pl_tags=[
                    "search-reporter",
                    self.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        user_msg = f"[Context]\n{context}"
        info = kwargs.get("info")
        if info:
            user_msg += f"\n[Info]\n{info}"

        chat_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(SEARCH_REPORTER_PROMPT),
                HumanMessagePromptTemplate.from_template(user_msg),
            ]
        )

        res = (
            chat_model.predict_with_msgs(chat_prompt)[0]
            .text.replace("[Summary]", "")
            .strip()
        )

        logger.info(f"generate search report for {self.user_id}: {res}")

        return res


if __name__ == "__main__":
    planer = SearchPlaner(user_id="test")
    plan = planer.generate(
        context="User: I have doubts about my own abilities, and I feel confused about the path ahead.",
        plan="""[Plan] Objective: Provide support and guidance to the user in overcoming self-doubt and confusion about their future path.
        
1.  Show empathy and understanding:
- Acknowledge the user's feelings of self-doubt and confusion.
- Express empathy to create a supportive environment.

2.  Explore the reasons behind the doubts and confusion:
- Ask open-ended questions to encourage the user to share their concerns.
- Listen actively and show genuine interest in understanding their perspective.

3.  Provide reassurance and encouragement:
- Highlight the user's strengths and past achievements.
- Offer words of encouragement to boost their confidence.

4.  Offer guidance and resources:
- Share personal experiences or stories of others who have overcome similar challenges.
- Provide resources such as articles, books, or online courses that can help the user gain clarity and confidence.

5.  Help the user identify their interests and goals:
- Ask questions to help the user reflect on their passions and interests.
- Encourage them to set realistic goals and break them down into manageable steps.

6.  Suggest seeking support from others:
- Recommend talking to a mentor, counselor, or trusted friend who can provide guidance.
- Emphasize the importance of building a support network.

7.  Summarize and provide next steps:
- Recap the key points discussed during the conversation.
- Offer suggestions for the user to take action, such as creating a plan or seeking further assistance.

8.  Follow up:
- Offer to continue the conversation or check in on the user's progress at a later time.
- Provide contact information or resources for ongoing support if needed.""",
    )
    print(plan)
    for item in plan:
        print(item)

    worker = SearchWorker(user_id="test")
    docs = worker.search(plan, score_threshold=0.3)
    info = dict_to_list(docs)

    reporter = SearchReporter(user_id="test")
    report = reporter.generate(
        context="User: I have doubts about my own abilities, and I feel confused about the path ahead.",
        info="\n".join(info),
    )
    print(report)

    # reporter = SearchReporter(user_id="test")
    # report = reporter.generate(
    #     context="User: I have doubts about my own abilities, and I feel confused about the path ahead.",
    #     info="""[Query] Have you achieved any notable accomplishments in the past that you're proud of?
    #     [Evidence] The user got accepted into postgraduate studies successfully.
    #     [Query] What specific aspects or areas are causing you the most confusion?
    #     [Evidence] The user finds it hard to make progress in the research.
    #     [Query] What are some of your interests or passions?
    #     [Evidence] The user is still passionate about the research.""",
    # )
    # print(report)
