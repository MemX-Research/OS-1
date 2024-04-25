import json
from langchain.embeddings import HuggingFaceEmbeddings
import argparse


class EmbeddingServer:
    def __init__(self, model_name, device="cuda:4"):
        print(f"Load model from `{model_name}` on `{device}`")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
            encode_kwargs={"show_progress_bar": False, "normalize_embeddings": True},
        )

    def inference(self, text):
        embeds = self.embedding_model.embed_query(text)
        return embeds


if __name__ == "__main__":
    import gradio as gr

    paser = argparse.ArgumentParser()
    paser.add_argument(
        "--model_name",
        type=str,
        default="/home/deploy/repo/multi-qa-mpnet-base-dot-v1",
    )
    paser.add_argument("--device", type=str, default="cuda")
    paser.add_argument("--port", type=int, default=7895)
    
    args = paser.parse_args()

    EMBED = EmbeddingServer(args.model_name, args.device)

    inputs = ["text"]
    outputs = ["json"]

    gr.Interface(fn=EMBED.inference, inputs=inputs, outputs=outputs).launch(
        server_name="0.0.0.0", server_port=args.port
    )
