import torch
from PIL import Image
from transformers import Blip2Processor, Blip2ForConditionalGeneration


class Blip2:
    def __init__(
        self,
        device="cuda:2",
        model="Salesforce/blip2-opt-2.7b",
    ):
        print("Initializing Blip2 to %s" % device)
        self.device = device
        self.processor = Blip2Processor.from_pretrained(model)
        self.model = (
            Blip2ForConditionalGeneration.from_pretrained(model).to(self.device).eval()
        )

    def image_caption(self, image: Image) -> str:
        inputs = self.processor(image, return_tensors="pt").to(self.device)
        generated_ids = self.model.generate(**inputs, max_new_tokens=64)
        generated_text = self.processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0].strip()
        return generated_text

    def vqa(self, image: Image, question: str) -> str:
        inputs = self.processor(
            image, f"Question: {question} Answer:", return_tensors="pt"
        ).to(self.device)
        generated_ids = self.model.generate(**inputs, max_new_tokens=64)
        generated_text = self.processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0].strip()
        return generated_text

    def inference(self, image: Image, task_type: str, question: str) -> str:
        if task_type == "Image Captioning":
            return self.image_caption(image)
        elif task_type == "Visual Question Answering":
            return self.vqa(image, question)
        else:
            raise NotImplementedError


if __name__ == "__main__":
    import gradio as gr

    Blip2Tool = Blip2()

    inputs = [
        gr.components.Image(type="pil"),
        gr.components.Radio(
            choices=["Image Captioning", "Visual Question Answering"],
            type="value",
            label="Task",
        ),
        gr.components.Textbox(lines=1, label="Question"),
    ]
    outputs = ["text"]
    gr.Interface(fn=Blip2Tool.inference, inputs=inputs, outputs=outputs).launch(
        server_name="0.0.0.0", server_port=7891
    )
