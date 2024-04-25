from pymilvus import Collection
from pymilvus import connections


class MilvusClient:
    def __init__(self, host="localhost", port="19530", **kwargs):
        connections.connect(host=host, port=port, **kwargs)

    @staticmethod
    def delete_entity(collection_name, expr):
        Collection(collection_name).delete(expr)

    @staticmethod
    def query_entity(collection_name, expr, **kwargs):
        return Collection(collection_name).query(expr, timeout=3.0, **kwargs)


if __name__ == "__main__":
    from pymilvus import utility

    # if utility.has_collection("LangChainCollection"):
    #     utility.drop_collection("LangChainCollection")

    connections.connect(host="localhost", port="19530")
    print(utility.list_collections())
    # print(Collection("LangChainCollection").schema)
    #
    # res = MilvusClient.query_entity(
    #     collection_name="LangChainCollection",
    #     expr='user_id == "test1" and memory_id == "1683860725670_c6612d2d-0706-453a-8602-dd384c8267ee"',
    #     output_fields=["user_id", "memory_id", "text"],
    # )
    # print(res)
    #
    # for item in res:
    #     MilvusClient.delete_entity(
    #         collection_name="LangChainCollection",
    #         expr=f'pk in [{item["pk"]}]',
    #     )
