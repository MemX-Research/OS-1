import cv2
import numpy as np
from PIL import Image

from .rpn_api import RPNAttentionTool


def open_pil_image(image_path: str) -> Image:
    return Image.open(image_path).convert("RGB")


def pil2cv(pil_image: Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(pil_image), cv2.COLOR_RGB2BGR)


def cv2pil(cv_image: np.ndarray) -> Image:
    return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))


def get_attended_image(image: Image, gaze_x: float, gaze_y: float) -> Image:
    cv_image = pil2cv(image)
    point_x = int(cv_image.shape[1] * gaze_x)
    point_y = int(cv_image.shape[0] * gaze_y)
    cv2.circle(cv_image, (point_x, point_y), 20, (0, 0, 255), 10)
    pil_image = cv2pil(cv_image)
    # box = VisualGroundingTool.inference(pil_image)
    box = RPNAttentionTool.inference(pil_image, gaze_x, gaze_y)
    if box == [0, 0, 0, 0]:
        return image, image
    box = [int(x) for x in box]
    visual_image = cv2pil(cv2.rectangle(cv_image, box[:2], box[2:], (0, 255, 0), 2, 4))
    attended_image = image.crop(box)
    return visual_image, attended_image
