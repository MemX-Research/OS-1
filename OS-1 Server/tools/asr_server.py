import os

import jax.numpy as jnp
import torch
import whisper
from whisper_jax import FlaxWhisperPipline

os.environ["XLA_FLAGS"] = "--xla_gpu_force_compilation_parallelism=1"
os.environ["CUDA_VISIBLE_DEVICES"] = "6"


class Whisper:
    def __init__(
        self,
        model="base",
        device="cuda:1",
    ):
        print("Initializing Whisper to %s" % device)
        self.model = whisper.load_model(name=model, device=device, in_memory=True)

    def audio2text(self, audio) -> str:
        result = self.model.transcribe(audio=audio, fp16=torch.cuda.is_available())
        return result["text"].strip()


class WhisperJAX:
    def __init__(self, model="openai/whisper-large-v2"):
        print("Initializing Whisper JAX")
        self.pipeline = FlaxWhisperPipline(model, dtype=jnp.bfloat16)

    def audio2text(self, audio) -> str:
        result = self.pipeline(audio, task="transcribe")
        return result["text"].strip()


if __name__ == "__main__":
    import gradio as gr

    # asr = Whisper()
    asr = WhisperJAX()

    inputs = [gr.components.Audio(type="filepath")]
    outputs = ["text"]

    gr.Interface(fn=asr.audio2text, inputs=inputs, outputs=outputs).launch(
        server_name="0.0.0.0", server_port=7890
    )
