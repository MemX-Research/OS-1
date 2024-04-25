from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration


class ImageCaptioning:
    def __init__(self, device="cpu", model="Salesforce/blip-image-captioning-base"):
        print("Initializing ImageCaptioning to %s" % device)
        self.device = device
        self.processor = BlipProcessor.from_pretrained(model)
        self.model = BlipForConditionalGeneration.from_pretrained(model).to(self.device)

    def inference(self, image: Image) -> str:
        inputs = self.processor(image, return_tensors="pt").to(self.device)
        outputs = self.model.generate(**inputs, max_new_tokens=64)
        captions = self.processor.decode(outputs[0], skip_special_tokens=True)
        return captions


# ImageCaptionTool = ImageCaptioning()
# ImageCaptionTool = ImageCaptioning("cuda:5")
