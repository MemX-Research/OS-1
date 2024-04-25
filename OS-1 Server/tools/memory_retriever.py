from copy import deepcopy
from datetime import datetime
from typing import Any, List, Tuple, Optional

from langchain.retrievers import TimeWeightedVectorStoreRetriever
from langchain.schema import Document
from langchain.vectorstores import Milvus

from tools.milvus_client import MilvusClient


class MilvusWrapper(Milvus):
    def __init__(self, **kwargs: Any):
        # use Inner Product for similarity search
        # search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
        # index_params = {
        #     "metric_type": "IP",
        #     "index_type": "HNSW",
        #     "params": {"nlist": 64},
        # }
        search_params = {"metric_type": "IP"}
        index_params = {
            "metric_type": "IP",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 64},
        }
        super().__init__(
            search_params=search_params, index_params=index_params, **kwargs
        )

    def _similarity_search_with_relevance_scores(
        self,
        query: str,
        k: int = 4,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        docs_and_similarities = self.similarity_search_with_score(
            query=query, k=k, **kwargs
        )
        results = []
        for doc, similarity in docs_and_similarities:
            # NOTE: similarity score can be further defined by adding {"score_threshold": 0.8} in search_kwargs
            if similarity < 0.2:
                continue
            results.append((doc, similarity))
        return results


class TimeWeightedMemoryRetriever(TimeWeightedVectorStoreRetriever):
    @staticmethod
    def _get_hours_passed(current_time: int, ref_time: int) -> float:
        return (current_time - ref_time) / 3600000

    def _get_combined_score(
        self,
        document: Document,
        vector_relevance: Optional[float],
        current_time: int,
    ) -> float:
        """Return the combined score for a document."""
        hours_passed = self._get_hours_passed(
            current_time,
            document.metadata["last_accessed_at"],
        )
        score = (1.0 - self.decay_rate) ** hours_passed
        # score = 0
        # logger.info(f"get_combined_score `time score`: {score}, {document}")
        for key in self.other_score_keys:
            if key in document.metadata:
                score += document.metadata[key] / 10
                # logger.info(
                #     f"get_combined_score `{key} score`: {document.metadata[key]}, {document}"
                # )
        if vector_relevance is not None:
            score += vector_relevance
            # logger.info(
            #     f"get_combined_score `relevance score`: {vector_relevance}, {document}"
            # )
        return score

    def get_relevant_documents(
        self, query: str, return_score=False, update_time=True
    ) -> List[Document]:
        """Return documents that are relevant to the query."""
        current_time = int(datetime.timestamp(datetime.now()) * 1000)
        result = []

        docs_and_scores = self.vectorstore.similarity_search_with_relevance_scores(
            query, k=self.k, **self.search_kwargs
        )

        rescored_docs = [
            (doc, self._get_combined_score(doc, relevance, current_time))
            for doc, relevance in docs_and_scores
        ]
        rescored_docs.sort(key=lambda x: x[1], reverse=True)

        # Ensure frequently accessed memories aren't forgotten
        for doc, score in rescored_docs[: self.k]:
            doc.metadata["last_accessed_at"] = current_time
            if return_score:
                doc.metadata["_score"] = score
            result.append(doc)
            # logger.info(f"get_relevant_documents score: {score}, {doc}")

        if len(result) <= 0:
            return result
        if update_time:
            self.update_doc_time(result)

        return result

    def update_doc_time(self, docs):
        memory_ids = [f'"{doc.metadata["memory_id"]}"' for doc in docs]
        if len(memory_ids) <= 0:
            return

        memory_ids_str = f'[{",".join(memory_ids)}]'
        res = MilvusClient().query_entity(
            collection_name=self.vectorstore.collection_name,
            expr=f"memory_id in {memory_ids_str}",
        )
        if len(res) <= 0:
            return

        pks = [item["pk"] for item in res]
        MilvusClient().delete_entity(
            collection_name=self.vectorstore.collection_name,
            expr=f"pk in {pks}",
        )
        self.add_documents(documents=docs)
        return

    def add_documents(self, documents: List[Document], **kwargs: Any) -> List[str]:
        """Add documents to vectorstore."""
        current_time = kwargs.get(
            "current_time", int(datetime.timestamp(datetime.now()) * 1000)
        )
        # Avoid mutating input documents
        dup_docs = [deepcopy(d) for d in documents]
        for doc in dup_docs:
            if "last_accessed_at" not in doc.metadata:
                doc.metadata["last_accessed_at"] = current_time
        return self.vectorstore.add_documents(dup_docs, **kwargs)

    async def aget_relevant_documents(self, query: str) -> List[Document]:
        """Return documents that are relevant to the query."""
        pass


class MemoryRetrieverWithIndex(TimeWeightedVectorStoreRetriever):
    def get_relevant_documents(self, query: str, return_score=False) -> List[Document]:
        """Return documents that are relevant to the query."""
        current_time = int(datetime.timestamp(datetime.now()) * 1000)
        result = []

        docs_and_scores = self.vectorstore.similarity_search_with_relevance_scores(
            query, **self.search_kwargs
        )  # [(doc, score), ...]

        rescored_docs = docs_and_scores
        rescored_docs.sort(key=lambda x: x[1], reverse=True)

        for doc, score in rescored_docs[: self.k]:
            if return_score:
                doc.metadata["_score"] = score
            result.append(doc)

        return result

    def add_documents(self, documents: List[Document], **kwargs: Any) -> List[str]:
        """Add documents to vectorstore."""
        current_time = kwargs.get(
            "current_time", int(datetime.timestamp(datetime.now()) * 1000)
        )
        # Avoid mutating input documents
        dup_docs = [deepcopy(d) for d in documents]
        for doc in dup_docs:
            if "last_accessed_at" not in doc.metadata:
                doc.metadata["last_accessed_at"] = current_time
        return self.vectorstore.add_documents(dup_docs, **kwargs)

    def retrieve_by_time_of_day(self, current_time: int):
        pass


if __name__ == "__main__":
    from openai_api import get_openai_embedding
    from uuid import uuid4

    current_time = int(datetime.timestamp(datetime.now()) * 1000)

    examples = [
        Document(
            page_content="""in a shopping mall, I am standing in front of a claw machine with various stuffed animals inside. I am eyeing a cute pink teddy bear stuck in the corner. I insert a few coins and control the claw to grab the teddy bear. I shout "Come on, baby!" as I press the button. The claw misses the teddy bear and I let out a sigh. A stranger next to me says "Don't worry, you'll get it next time." We start talking about our favorite stuffed animals from childhood. I realize that winning the toy is not as important as the joy of playing the game and connecting with others.""",
            metadata={
                "last_accessed_at": current_time,
                "user_id": "test1",
                "memory_id": f"{current_time}_{uuid4()}",
            },
        ),
        Document(
            page_content="""in an amusement park, I am standing in front of a giant claw machine with a huge unicorn plushie inside. I am strategizing how to grab the unicorn with the claw. I press the button and the claw successfully grabs the unicorn. I jump up and down in excitement and shout "Yes!" A group of kids nearby start cheering for me. Their parents come over and congratulate me on my win. We start talking about other fun games in the park and exchange tips on how to win. I realize that sharing the experience of playing games and celebrating small victories with others can create a sense of community and joy.""",
            metadata={
                "last_accessed_at": 1652324653000,
                "user_id": "test1",
                "memory_id": f"{current_time}_{uuid4()}",
            },
        ),
        Document(
            page_content="""in a carnival, I am standing in front of a claw machine filled with colorful balloons. I am trying to grab a purple balloon with a smiley face printed on it. The claw misses the balloon and it floats away. I feel disappointed and frustrated. A friend comes over and asks me what happened. I complain about how the claw machine is rigged and how I never win anything. My friend listens patiently and then says "Maybe it's not about winning or losing, but about having fun and trying something new." We decide to try a different game and end up having a blast. I realize that focusing too much on winning can blind us from enjoying the process and discovering new things.""",
            metadata={
                "last_accessed_at": 1652324653000,
                "user_id": "test1",
                "memory_id": f"{current_time}_{uuid4()}",
            },
        ),
    ]
    # print(examples)

    # collection_name = "LangChainCollection"
    collection_name = "memory_index_test"
    query = "car"
    memory_retriever = TimeWeightedMemoryRetriever(
        vectorstore=MilvusWrapper(
            embedding_function=get_openai_embedding(),
            collection_name=collection_name,
            consistency_level="Strong",
        ),
        k=3,
        search_kwargs={
            "expr": 'user_id in ["new-mem"]',
            "score_threshold": 0.8,
        },
        other_score_keys=["importance"],
    )
    # memory_retriever.add_documents(examples)
    res = memory_retriever.get_relevant_documents(query)
    print(res)
    for doc in res:
        print(doc)

    # res = MilvusClient().query_entity(
    #     collection_name=collection_name,
    #     expr='user_id in ["new-mem"]',
    #     output_fields=["memory_id"],
    # )
    # print(res)
    # print(len(res))
