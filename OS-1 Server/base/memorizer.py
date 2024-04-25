import time
from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from threading import Thread
from typing import Any, List, Optional
from uuid import uuid4

import numpy as np
import pymongo
from langchain.schema import Document

from base.tag import Tag
from tools.log import logger
from tools.memory_retriever import (
    MemoryRetrieverWithIndex,
    MilvusWrapper,
    TimeWeightedMemoryRetriever,
)
from tools.mongo import MongoClientProxy
from tools.openai_api import EmbeddingModel
from tools.time_fmt import (
    PeriodOfDay,
    get_relative_time,
    get_timestamp,
    timestamp_to_str,
)


class MemoryType(Enum):
    INDEX = 0
    ONE_MINUTE = 1
    TEN_MINUTES = 2
    ONE_HOUR = 3
    THREE_HOURS = 4
    ONE_DAY = 5
    ONE_WEEK = 6
    ONE_MONTH = 7
    ONE_YEAR = 8
    CONVERSATION = 9
    CONVERSATION_UNFINISHED = 10
    PERSONA = 11
    ASSOCIATIVE_MEMORY = 12

    @property
    def vectordb_name(self):
        if self == MemoryType.PERSONA:
            # return "persona_new"
            return "persona_pilot_study"
        elif self == MemoryType.INDEX:
            # return "memory_index_test"
            return "memory_pilot_study"
        elif self == MemoryType.ASSOCIATIVE_MEMORY:
            return "associative_memory"
        else:
            # return "memory"
            return "memory_default"


class DayOfWeek(Enum):
    SUNDAY = 1
    MONDAY = 2
    TUESDAY = 3
    WEDNESDAY = 4
    THURSDAY = 5
    FRIDAY = 6
    SATURDAY = 7


def get_duration(memory_type: MemoryType):
    if memory_type == MemoryType.ONE_MINUTE:
        return 60 * 1000
    elif memory_type == MemoryType.TEN_MINUTES:
        return 10 * 60 * 1000
    elif memory_type == MemoryType.ONE_HOUR:
        return 60 * 60 * 1000
    elif memory_type == MemoryType.THREE_HOURS:
        return 3 * 60 * 60 * 1000
    elif memory_type == MemoryType.ONE_DAY:
        return 23 * 60 * 60 * 1000  # 4am ~ 3am
    else:
        raise Exception(f"MemoryType {memory_type} not implemented")


class Memory(Tag):
    memory_id: Optional[str] = None
    memory_type: Optional[int] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    content: Optional[str] = None
    detail: Optional[str] = None
    importance: Optional[float] = None
    metadata: Optional[dict] = dict()

    def format(self, absolute_time=True, including_today=False, now=None):
        if absolute_time:
            return f"{timestamp_to_str(self.start_time)} - {timestamp_to_str(self.end_time)}: {self.content}"
        return f"{get_relative_time(self.start_time, including_today=including_today, now=now)} {self.content}"

    @classmethod
    def format_list(cls, res, absolute_time=True, now=None):
        memories = [
            cls.parse_obj(item).format(absolute_time=absolute_time, now=now)
            for item in res
        ]
        return "\n".join(memories)

    def format_event(self, including_time=True):
        res = ""
        if including_time:
            res += f"{timestamp_to_str(self.start_time)} - {timestamp_to_str(self.end_time)}: "
        if self.content is not None and self.detail is not None:
            return f"{res}Summary: {self.content} Detail: {self.detail}"
        if self.detail is not None:
            return f"{res}{self.detail}"
        return f"{res}Summary: {self.content}"

    @classmethod
    def format_event_list(cls, res, including_time=True):
        memories = [cls.parse_obj(item).format_event(including_time) for item in res]
        return "\n".join(memories)

    def save_memory(self):
        if self.memory_id is None:
            self.memory_id = f"{self.user_id}_{self.current_time}_{uuid4()}"
        return MongoClientProxy.get_client()["memx"]["memory"].insert_one(self.dict())

    @staticmethod
    def find_memory(*args: Any, **kwargs: Any):
        return MongoClientProxy.get_client()["memx"]["memory"].find(*args, **kwargs)

    @classmethod
    def get_memory_list_by_day(
        cls,
        user_id: str,
        day: DayOfWeek,  # 1 (Sunday) and 7 (Saturday)
        start: int,
        end: int,
        memory_type: MemoryType = MemoryType.ONE_DAY,
    ) -> List[dict]:
        """{"_id": date, "event_list": ["start_time - end_time: content"]}"""
        res = MongoClientProxy.get_client()["memx"]["memory"].aggregate(
            [
                {
                    "$match": {
                        "user_id": user_id,
                        "memory_type": memory_type.value,
                        "start_time": {"$gte": start, "$lt": end},
                    }
                },
                {
                    "$addFields": {
                        "start_date": {
                            "$add": [datetime.fromtimestamp(0), "$start_time"]
                        },
                        "end_date": {"$add": [datetime.fromtimestamp(0), "$end_time"]},
                        "day": {
                            "$dayOfWeek": {
                                "$add": [datetime.fromtimestamp(0), "$start_time"]
                            }  # 1 (Sunday) and 7 (Saturday)
                        },
                    },
                },
                {"$match": {"day": day.value}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {"format": "%m-%d", "date": "$start_date"}
                        },
                        "total": {"$sum": 1},
                        "event_list": {
                            "$push": {
                                "$concat": [
                                    {
                                        "$dateToString": {
                                            "format": "%H:%M-",
                                            "date": "$start_date",
                                        }
                                    },
                                    {
                                        "$dateToString": {
                                            "format": "%H:%M, ",
                                            "date": "$end_date",
                                        }
                                    },
                                    "$content",
                                ]
                            }
                        },
                    }
                },
            ]
        )
        res = list(res)
        for item in res:
            item["event_list"] = list(set(item["event_list"]))
            item["event_list"].sort()
        return res

    @classmethod
    def get_memory_list_by_period_of_day(
        cls,
        user_id: str,
        period: PeriodOfDay,
        start: int,
        end: int,
        memory_type: MemoryType = MemoryType.ONE_DAY,
    ) -> List[dict]:
        """{"_id": date, "event_list": ["start_time - end_time: content"]}"""
        offset = -5
        period_with_offset = period.range_with_offset(offset)
        res = MongoClientProxy.get_client()["memx"]["memory"].aggregate(
            [
                {
                    "$match": {
                        "user_id": user_id,
                        "memory_type": memory_type.value,
                        "start_time": {"$gte": start, "$lt": end},
                    }
                },
                {"$sort": {"start_time": 1, "end_time": 1}},
                {
                    "$addFields": {
                        "start_date": {
                            "$add": [datetime.fromtimestamp(0), "$start_time"]
                        },
                        "end_date": {"$add": [datetime.fromtimestamp(0), "$end_time"]},
                        "hour": {
                            "$hour": {
                                "$add": [
                                    datetime.fromtimestamp(0) + timedelta(hours=offset),
                                    "$start_time",
                                ]
                            }
                        },
                    }
                },
                {
                    "$match": {
                        "hour": {
                            "$gte": period_with_offset[0],
                            "$lt": period_with_offset[1],
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {"format": "%m-%d", "date": "$start_date"}
                        },
                        "total": {"$sum": 1},
                        "event_list": {
                            "$push": {
                                "$concat": [
                                    {
                                        "$dateToString": {
                                            "format": "%H:%M-",
                                            "date": "$start_date",
                                        }
                                    },
                                    {
                                        "$dateToString": {
                                            "format": "%H:%M, ",
                                            "date": "$end_date",
                                        }
                                    },
                                    "$content",
                                ]
                            }
                        },
                    }
                },
            ]
        )
        res = list(res)
        for item in res:
            item["event_list"] = list(set(item["event_list"]))
            item["event_list"].sort()
        return res

    @classmethod
    def get_memory_by_duration(
        cls,
        user_id: str,
        memory_type: MemoryType,
        start: int,
        end: int,
        limit: int = 10,
        filer: dict = {},
    ):
        res = list(
            cls.find_memory(
                {
                    "user_id": user_id,
                    "memory_type": memory_type.value,
                    "start_time": {
                        "$gte": start,
                    },
                    "end_time": {
                        "$lte": end,
                    },
                    **filer,
                },
                {
                    "_id": 0,
                },
            )
            .sort("end_time", pymongo.DESCENDING)
            .limit(limit)
        )
        res.reverse()
        return res

    def save_memory_to_vectordb(self, check_exists=False):
        if self.content is None or self.content == "":
            logger.info("memory content is none or empty")
            return
        memory_retriever = TimeWeightedMemoryRetriever(
            vectorstore=MilvusWrapper(
                embedding_function=EmbeddingModel,
                collection_name=MemoryType(self.memory_type).vectordb_name,
                consistency_level="Strong",
            ),
        )
        if check_exists:
            memory_retriever.k = 1
            memory_retriever.search_kwargs = {
                "expr": f'user_id == "{self.user_id}"',
                "score_threshold": 0.95,
            }
            res = memory_retriever.get_relevant_documents(
                query=self.content, return_score=False, update_time=False
            )
            if len(res) > 0:
                logger.info(f"Memory `{self.content}` already exists")
                return
        memory_retriever.add_documents(
            [
                Document(
                    page_content=self.content,
                    metadata={
                        "last_accessed_at": get_timestamp(),
                        "user_id": self.user_id,
                        "memory_id": self.memory_id,
                        "memory_type": self.memory_type,
                        "start_time": self.start_time,
                        "end_time": self.end_time,
                        "importance": self.importance,
                    },
                )
            ]
        )

    def save_memory_to_vectordb_with_index(self, index: str):
        memory_retriever = TimeWeightedMemoryRetriever(
            vectorstore=MilvusWrapper(
                embedding_function=EmbeddingModel,
                collection_name=MemoryType.INDEX.vectordb_name,
                consistency_level="Strong",
            ),
        )
        memory_retriever.add_documents(
            [
                Document(
                    page_content=index,
                    metadata={
                        "last_accessed_at": get_timestamp(),
                        "user_id": self.user_id,
                        "memory_id": self.memory_id,
                        "memory_type": self.memory_type,
                        "start_time": self.start_time,
                        "end_time": self.end_time,
                        "importance": self.importance,
                    },
                )
            ]
        )

    @staticmethod
    def query_memory_from_vectordb(
        user_id: str, memory_types: List[MemoryType], query: str, k=1
    ):
        memory_retriever = TimeWeightedMemoryRetriever(
            vectorstore=MilvusWrapper(
                embedding_function=EmbeddingModel,
                collection_name=memory_types[0].vectordb_name,
                consistency_level="Strong",
            ),
            k=k,
            search_kwargs={
                "expr": f'user_id == "{user_id}" and memory_type in {[memory_type.value for memory_type in memory_types]}'
            },
            other_score_keys=["importance"],
        )
        return memory_retriever.get_relevant_documents(query=query)

    @staticmethod
    def query_associative_memory_from_vectordb(
        user_id: str,
        query: str,
        k=1,
        score_threshold=0.75,
    ):
        memory_retriever = TimeWeightedMemoryRetriever(
            vectorstore=MilvusWrapper(
                embedding_function=EmbeddingModel,
                collection_name=MemoryType.ASSOCIATIVE_MEMORY.vectordb_name,
                consistency_level="Strong",
            ),
            k=k,
            search_kwargs={
                "expr": f'user_id == "{user_id}"',
                "score_threshold": score_threshold,
            },
        )
        return memory_retriever.get_relevant_documents(query=query, update_time=False)

    @staticmethod
    def query_persona_from_vectordb(
        user_id: str, query: str, k=1, score_threshold=0.75, start_time=0
    ):
        memory_retriever = TimeWeightedMemoryRetriever(
            vectorstore=MilvusWrapper(
                embedding_function=EmbeddingModel,
                collection_name=MemoryType.PERSONA.vectordb_name,
                consistency_level="Strong",
            ),
            k=k,
            search_kwargs={
                "expr": f'user_id == "{user_id}" and start_time > {start_time}',
                "score_threshold": score_threshold,
            },
        )
        return memory_retriever.get_relevant_documents(query=query, update_time=False)

    @staticmethod
    def sort_index_by_context(
        context_text: str,
        indexes: List[Document],
        threshold=0.3,
    ):
        idx_strs = [index.page_content for index in indexes]
        index_embeds = EmbeddingModel.embed_documents(idx_strs)
        text_embed = EmbeddingModel.embed_query(context_text)
        scores = np.dot(index_embeds, text_embed)
        sorted_indexes_with_scores = sorted(
            zip(scores, indexes), key=lambda x: x[0], reverse=True
        )
        print(sorted_indexes_with_scores)
        sorted_indexes = [
            index for score, index in sorted_indexes_with_scores if score > threshold
        ]
        return sorted_indexes

    @staticmethod
    def query_memory_from_vectordb_by_indexes(
        user_id: str,
        indexes: List[str],
        mem_k=3,
        score_threshold=0.8,
        collection_name=None,
        context_text=None,
    ):
        collection_name = (
            collection_name if collection_name else MemoryType.INDEX.vectordb_name
        )
        index_k = 10
        memory_retriever = MemoryRetrieverWithIndex(
            vectorstore=MilvusWrapper(
                embedding_function=EmbeddingModel,
                collection_name=collection_name,
                consistency_level="Strong",
            ),
            k=index_k,
            search_kwargs={
                "expr": f'user_id == "{user_id}"',
                "score_threshold": score_threshold,
            },
            other_score_keys=["importance"],
        )
        # query indexes from vectordb
        idx_docs = []

        def query_vectordb(query):
            idxes = memory_retriever.get_relevant_documents(
                query=query, return_score=True
            )
            idx_docs.extend(idxes)

        start = time.time()

        thread_list = []

        for query in indexes:
            thread = Thread(
                target=query_vectordb,
                args=(query,),
            )
            thread.start()
            thread_list.append(thread)
        for thread in thread_list:
            thread.join()

        # filter indexes by context
        if context_text and len(idx_docs) > 0:
            idx_docs = Memory.sort_index_by_context(
                context_text, idx_docs, threshold=0.3
            )

        memory_ids = []
        for idx in idx_docs:
            memory_id = idx.metadata["memory_id"]
            score = idx.metadata["_score"]
            if memory_id not in memory_ids:
                memory_ids.append(memory_id)
        vectordb_time = time.time() - start

        # sort by score
        # memid_score_list = list(index_score_dict.items())
        # memid_score_list.sort(key=lambda x: x[1], reverse=True)
        # memory_ids = list(index_score_dict.keys())

        start = time.time()
        docs = Memory.get_memory_from_mongo(memory_ids[:mem_k])
        mongo_time = time.time() - start
        logger.info(
            f"query {len(docs)} memory, cost time: vectordb({len(indexes)}) {vectordb_time:.2f}s, mongo({mem_k}) {mongo_time:.2f}s"
        )
        return docs

    @staticmethod
    def get_memory_from_mongo(memory_ids: List):
        # get memory from mongo
        docs = []

        mems = Memory().find_memory({"memory_id": {"$in": memory_ids}})
        mems = list(mems)
        # return in order
        for memory_id in memory_ids:
            for mem in mems:
                if mem["memory_id"] == memory_id:
                    mem["metadata"]["start_time"] = mem["start_time"]
                    doc = Document(
                        page_content=mem["content"], metadata=mem["metadata"]
                    )
                    docs.append(doc)
                    break

        # for mem in mems:
        #     mem["metadata"]["start_time"] = mem["start_time"]
        #     doc = Document(page_content=mem["content"], metadata=mem["metadata"])
        #     docs.append(doc)

        return docs

    @staticmethod
    def format_memory_docs(docs: List[Document], now: int = None):
        return "\n".join(
            [
                f'{get_relative_time(doc.metadata["start_time"], including_today=False, now=now)} {doc.page_content}'
                for doc in docs
            ]
        )


class MemoryGenerator(metaclass=ABCMeta):
    @abstractmethod
    def generate_memory(self):
        pass


if __name__ == "__main__":
    mem = Memory(
        user_id="test",
        memory_type=MemoryType.ASSOCIATIVE_MEMORY.value,
        content="The user got accepted into postgraduate studies successfully.",
        memory_id="memory_id",
        start_time=get_timestamp() - 24 * 60 * 60 * 1000 * 1,
        end_time=get_timestamp(),
        importance=0.5,
    )
    mem.save_memory_to_vectordb(check_exists=True)

    docs = Memory().query_associative_memory_from_vectordb(
        user_id="test",
        query="Have you achieved any notable accomplishments in the past that you're proud of?",
        score_threshold=0.4,
    )
    print(docs)

    # start_time = get_timestamp() - 24 * 60 * 60 * 1000 * 1
    # end_time = get_timestamp()
    # indexes = ["To The Sky", "flying house", "romantic sky", "music"]
    # res = Memory().query_memory_from_vectordb_by_indexes(
    #     "wangchengyu", indexes, mem_k=10, score_threshold=0.7
    # )
    #
    # print("==========")
    # for doc in res:
    #     print(doc.page_content)
