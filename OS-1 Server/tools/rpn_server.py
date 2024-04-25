import gradio as gr
import numpy as np
import torch
import torchvision
from PIL import Image, ImageDraw
from torchvision.models.detection import (
    FasterRCNN_ResNet50_FPN_Weights,
    fasterrcnn_resnet50_fpn,
)
from torchvision.models.detection.rpn import ImageList

# Load the pre-trained Faster R-CNN model
model = fasterrcnn_resnet50_fpn(weights=FasterRCNN_ResNet50_FPN_Weights.DEFAULT)

# Set the model to evaluation mode
model.eval()

# Move the model to the device (CPU or GPU)
device = torch.device("cuda:3") if torch.cuda.is_available() else torch.device("cpu")
model.to(device)


def filter_box_wh(boxes, w, h, min_w=0.05, min_h=0.05):
    """过滤掉太小的box"""
    w = (boxes[:, 2] - boxes[:, 0]) / w
    h = (boxes[:, 3] - boxes[:, 1]) / h
    ids = np.where((w > min_w) & (h > min_h))[0]
    return boxes[ids]


def is_in_box(box, point, padding=0):
    x1, y1, x2, y2 = box
    x, y = point
    if x1 - padding <= x <= x2 + padding and y1 - padding <= y <= y2 + padding:
        return True
    return False


def box_size(box):
    x1, y1, x2, y2 = box
    return (x2 - x1) * (y2 - y1)


def sort_box_by_size(boxes):
    box_sizes = [box_size(box) for box in boxes]
    sorted_ids = np.argsort(box_sizes)
    return boxes[sorted_ids]


def get_outer_rect(boxes):
    x1 = np.min(boxes[:, 0])
    y1 = np.min(boxes[:, 1])
    x2 = np.max(boxes[:, 2])
    y2 = np.max(boxes[:, 3])
    return [x1, y1, x2, y2]

@torch.inference_mode()
def inference(input_image: Image, gaze_x, gaze_y):
    gaze_point = [gaze_x, gaze_y]
    w, h = input_image.size
    gaze_point = [gaze_point[0] * w, gaze_point[1] * h]

    # Transform the input image to the expected format
    # input_image.filter(ImageFilter.GaussianBlur(radius=10))
    transform = torchvision.transforms.Compose(
        [
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize(
                [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
            ),
        ]
    )
    input_tensor = transform(input_image)

    input_tensor = input_tensor.to(device)
    input_tensor = input_tensor.unsqueeze(0)  # Add a batch dimension

    with torch.no_grad():
        rpn = model.rpn
        features = model.backbone(input_tensor)
        img_list = ImageList(
            input_tensor, [(input_tensor.shape[2], input_tensor.shape[3])]
        )
        proposals, _ = rpn(img_list, features)

    # Convert the proposals tensor to a list of numpy arrays
    proposals = proposals[0].cpu().detach().numpy()

    proposals = filter_box_wh(proposals, w, h, min_w=0.1, min_h=0.1)

    selected_proposals = []
    for box in proposals:
        if is_in_box(box, gaze_point, padding=10):
            selected_proposals.append(box)

    selected_proposals = np.array(selected_proposals)
    print("rpn:", len(selected_proposals))
    if len(selected_proposals) == 0:
        return input_image, [0, 0, w, h]
    # nms
    ids = torchvision.ops.nms(
        torch.from_numpy(selected_proposals), torch.ones(len(selected_proposals)), 0.4
    )
    selected_proposals = selected_proposals[ids]
    if selected_proposals.ndim == 1:
        selected_proposals = selected_proposals[np.newaxis, ...]
    print("nms:", len(selected_proposals))

    if len(selected_proposals) == 0:
        return input_image, [0, 0, w, h]
    selected_proposals = sort_box_by_size(selected_proposals)
    selected_proposals = selected_proposals[:8]

    # Draw the proposals on the input image
    draw = ImageDraw.Draw(input_image)
    for proposal in selected_proposals:
        x1, y1, x2, y2 = proposal
        draw.rectangle(((x1, y1), (x2, y2)), outline="red", width=3)

    outer_rect = get_outer_rect(selected_proposals)
    draw.rectangle(
        ((outer_rect[0], outer_rect[1]), (outer_rect[2], outer_rect[3])),
        outline="blue",
        width=3,
    )
    draw.ellipse(
        (
            gaze_point[0] - 20,
            gaze_point[1] - 20,
            gaze_point[0] + 20,
            gaze_point[1] + 20,
        ),
        fill="green",
    )

    # Show the input image with the region proposals
    input_image.save("proposals.jpg")
    return input_image, outer_rect


if __name__ == "__main__":
    inputs = [
        gr.components.Image(type="pil"),
        gr.components.Number(label="gaze_x"),
        gr.components.Number(label="gaze_y"),
    ]
    outputs = [gr.outputs.Image(type="pil"), "text"]
    gr.Interface(fn=inference, inputs=inputs, outputs=outputs, title="RPN").launch(
        server_name="0.0.0.0", server_port=7862
    )
