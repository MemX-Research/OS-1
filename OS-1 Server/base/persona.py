import datetime
import json
from typing import List

from bson import json_util
from langchain.schema import Document

from base.history import History, HumanProfile
from base.memorizer import Memory, MemoryType
from base.tag import Tag
from templates.conversation import USER_PERSONA_REFINE_PROMPT
from tools.helper import TextHelper
from tools.llm import ChatModel
from tools.log import logger
from tools.memory_retriever import MilvusWrapper, TimeWeightedMemoryRetriever
from tools.mongo import MongoClientProxy
from tools.openai_api import get_openai_chatgpt
from tools.time_fmt import get_past_timestamp, get_timestamp


class BasicPersona(Tag):
    BASIC_QUERIES = ["User's job", "User's personality"]
    OUTPUT_TYPE = ["job", "personality"]  # -> HumanProfile

    def retrieve_persona(self, query, score_threshold=0.5, k=8) -> List[Document]:
        docs = Memory().query_persona_from_vectordb(
            self.user_id,
            query=query,
            k=k,
            score_threshold=score_threshold,
            # start_time=get_past_timestamp(days=90),
        )

        sorted_docs = sorted(docs, key=lambda x: x.metadata["importance"], reverse=True)
        return sorted_docs

    def get_persona_prompt(self, query):
        prompt = f"About {query}:\n"

        docs = self.retrieve_persona(query)
        if len(docs) == 0:
            return ""
        if len(docs) > 0:
            for doc in docs:
                prompt += (
                    f"- {doc.page_content}, Confidence: {doc.metadata['importance']}\n"
                )
        return prompt

    def generate_basic_persona(self):
        persona_list = ""

        for q in self.BASIC_QUERIES:
            p = self.get_persona_prompt(q)
            persona_list += p
        if persona_list == "":
            logger.warning(f"no persona found for `{self.user_id}`")
            return

        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                max_tokens=2048,
                pl_tags=[
                    "persona-refine",
                    self.user_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )
        json_dict = {q: "" for q in self.OUTPUT_TYPE}

        system_prompt = USER_PERSONA_REFINE_PROMPT.format(
            persona_list=persona_list,
            json_format=json.dumps(json_dict, indent=2)
            .replace(r"{", r"{{")
            .replace(r"}", r"}}"),
        )

        # retry 1 times
        tries = 0
        while tries < 2:
            tries += 1
            try:
                res = chat_model.predict_with_prompt(prompt=system_prompt)
                persona_obj = TextHelper.parse_json(res)
                logger.info(
                    f"generate refined persona of `{self.user_id}`: {persona_obj}"
                )
                break

            except Exception as e:
                logger.error(f"error in summarizing conversation: {e}")
                logger.warning("retry with gpt-3.5-turbo-16k")
                chat_model.llm.model_name = "gpt-3.5-turbo-16k"
                chat_model.llm.max_tokens = 4096
                continue

        human_profile = HumanProfile.parse_obj(persona_obj)
        new_history = History(
            current_time=self.current_time,
            user_id=self.user_id,
            human_profile=human_profile,
        )
        new_history.save_history()

    def generate_task(self):
        res = History.get_latest_history(self.user_id, seconds=23 * 60 * 60, limit=1)
        if len(res) > 0:
            logger.info("history exists, skip generating task")
            return

        self.generate_basic_persona()


if __name__ == "__main__":
    BasicPersona(user_id="test").generate_basic_persona()
    res = History.get_latest_history("test", seconds=604800, limit=1)
    for item in res:
        history = History.parse_raw(json_util.dumps(item))
        human_profile = history.human_profile.dict(exclude_defaults=True)
        print(human_profile)
