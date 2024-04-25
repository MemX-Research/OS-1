from typing import List, Any
from pydantic import BaseModel, Extra
from langchain.embeddings.base import Embeddings
import requests


class CustomEmbeddings(BaseModel, Embeddings):
    base_url = ""

    def __init__(self, url="http://127.0.0.1:7895", **kwargs: Any):
        """Initialize the sentence_transformer."""
        super().__init__(**kwargs)

        self.base_url = url + "/run/predict"

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Compute doc embeddings using a HuggingFace transformer model.

        Args:
            texts: The list of texts to embed.

        Returns:
            List of embeddings, one for each text.
        """
        texts = list(map(lambda x: x.replace("\n", " "), texts))
        embeddings = []
        for text in texts:
            embedding = self.embed_query(text)
            embeddings.append(embedding)
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Compute query embeddings using a HuggingFace transformer model.

        Args:
            text: The text to embed.

        Returns:
            Embeddings for the text.
        """
        text = text.replace("\n", " ")
        data = {
            "data": [
                text,
            ]
        }
        response = requests.post(self.base_url, json=data).json()["data"][0]
        return response
