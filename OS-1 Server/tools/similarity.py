from typing import List

import numpy as np
import torch

from tools.openai_api import get_openai_embedding


def calc_similarity_matrix(texts: List[str]):
    texts_embed = get_openai_embedding().embed_documents(texts)
    texts_embed = torch.tensor(np.array(texts_embed))
    matrix = texts_embed / torch.norm(texts_embed, dim=-1, keepdim=True)
    similarity = torch.mm(matrix, matrix.T)
    return similarity


def is_texts_similar(texts: List[str], similarity_threshold=0.8, similarity_ratio=0.6):
    similarity_matrix = calc_similarity_matrix(texts)
    res = torch.gt(similarity_matrix[0], similarity_threshold)
    return torch.sum(res) / len(res) >= similarity_ratio


def text_cluster(texts: List[str], similarity_threshold=0.8):
    matrix = calc_similarity_matrix(texts)
    i = 0
    cluster_list = []
    while i < matrix.shape[0]:
        matrix[i][:i] = 1.0
        res = list(torch.gt(matrix[i], similarity_threshold))
        if False in res:
            j = res.index(False)
        else:
            j = matrix.shape[0]
        cluster_list.append((i, j))
        i = j
    return cluster_list
