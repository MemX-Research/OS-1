from PIL import Image
from transformers import BlipProcessor, BlipForQuestionAnswering


class VisualQuestionAnswering:
    def __init__(self, device="cpu", model="Salesforce/blip-vqa-base"):
        print("Initializing VisualQuestionAnswering to %s" % device)
        self.device = device
        self.processor = BlipProcessor.from_pretrained(model)
        self.model = BlipForQuestionAnswering.from_pretrained(model).to(self.device)

    def inference(self, image: Image, question: str) -> str:
        inputs = self.processor(image, question, return_tensors="pt").to(self.device)
        out = self.model.generate(**inputs, max_new_tokens=64)
        answers = self.processor.decode(out[0], skip_special_tokens=True)
        return answers


# VQATool = VisualQuestionAnswering()
# VQATool = VisualQuestionAnswering(device="cuda:6")
