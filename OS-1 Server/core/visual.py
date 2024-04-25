import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from base.conversation import Conversation
from base.visual import VisualContext, VisualImage, VisualPerceptron
from templates.context import EPISODIC_PROMPT
from tools.bs64 import image2bs64
from tools.helper import TextHelper
from tools.image_tool import get_attended_image
from tools.llava_api import LlavaVisualAssistant
from tools.llm import ChatModel
from tools.log import logger
from tools.openai_api import get_openai_chatgpt


class VisualContextRecognizer(VisualPerceptron):
    def recognize_context(self, visual_image: VisualImage) -> VisualContext:
        start = time.time()

        visual_context = VisualContext(
            current_time=visual_image.current_time,
            user_id=visual_image.user_id,
            gaze_point=visual_image.gaze_point,
        )

        pool = ThreadPoolExecutor(max_workers=3)

        attention_task = pool.submit(
            get_attended_image,
            visual_image.original_image.copy(),
            float(visual_image.gaze_point[0]),
            float(visual_image.gaze_point[1]),
        )

        scene_task = pool.submit(
            LlavaVisualAssistant.inference,
            visual_image.original_image.copy(),
        )

        visual_image.visual_image, visual_image.attended_image = attention_task.result()
        visual_context.attention = pool.submit(
            LlavaVisualAssistant.inference, visual_image.attended_image.copy()
        ).result()
        visual_context.scene = scene_task.result()

        pool.shutdown()

        visual_context.original_image = image2bs64(visual_image.original_image)
        visual_context.attended_image = image2bs64(visual_image.attended_image)
        visual_context.visual_image = image2bs64(visual_image.visual_image)

        logger.info(
            "save_context: {}, {:.2f}s, {}".format(
                visual_context.user_id,
                time.time() - start,
                visual_context.json(
                    exclude={"original_image", "attended_image", "visual_image"}
                ),
            )
        )
        return visual_context

    def generate_extra_context(self, scene: str, current_conversation: list) -> dict:
        conversation_str = Conversation.msgs_to_string(
            Conversation.format_list(current_conversation),
            ai_prefix="Samantha",
            human_prefix="User",
        ).strip()

        chat_model = ChatModel(
            llm=get_openai_chatgpt(
                temperature=0.0,
                max_tokens=256,
                pl_tags=[
                    "episodic-context",
                    datetime.now().strftime("%Y-%m-%d"),
                ],
            )
        )

        system_prompt = EPISODIC_PROMPT.format(
            scene=scene,
            conversation=conversation_str,
        )

        res = chat_model.predict_with_prompt(prompt=system_prompt)
        res_obj = TextHelper.parse_json(res)
        logger.info("generate_extra_context: {}".format(res_obj))
        for k in res_obj:
            res_obj[k] = res_obj[k].replace("User is", "").strip()

        return res_obj

    def recognize_context_with_conversation(
        self, visual_image: VisualImage
    ) -> VisualContext:
        start = time.time()

        visual_context = VisualContext(
            current_time=visual_image.current_time,
            user_id=visual_image.user_id,
            gaze_point=visual_image.gaze_point,
        )

        visual_image.visual_image = visual_image.original_image

        visual_context.scene = LlavaVisualAssistant.inference(
            visual_image.original_image.copy()
        )

        # infer `activity, location, emotion` with conversation
        current_conversations = Conversation.get_latest_conversation(
            user_id=visual_image.user_id,
            seconds=60 * 10,
            limit=3,
            end=visual_image.current_time,
        )
        if len(current_conversations) > 0 and visual_context.scene:
            try:
                extra_context = self.generate_extra_context(
                    visual_context.scene, current_conversations
                )
                visual_context.activity = extra_context.get("activity", None)
                visual_context.location = extra_context.get("location", None)
                visual_context.emotion = extra_context.get("emotion", None)

            except Exception as e:
                logger.error(
                    f"generate_extra_context error: {e}, {traceback.format_exc()}"
                )

        visual_context.original_image = image2bs64(visual_image.original_image)
        visual_context.visual_image = image2bs64(visual_image.visual_image)

        logger.info(
            "save_context: {}, {:.2f}s, {}".format(
                visual_context.user_id,
                time.time() - start,
                visual_context.json(
                    exclude={"original_image", "attended_image", "visual_image"}
                ),
            )
        )
        return visual_context


if __name__ == "__main__":
    from tools.image_tool import open_pil_image

    start = time.time()

    image_path = "./data/images/img_1.png"
    visual_image = VisualImage()
    visual_image.current_time = int(round(time.time() * 1000))
    visual_image.user_id = "test1"
    visual_image.original_image = open_pil_image(image_path)
    visual_image.gaze_point = (0.5, 0.5)

    visual_context_recognizer = VisualContextRecognizer()
    visual_context = visual_context_recognizer.recognize_context_with_conversation(
        visual_image
    )
    visual_context.save_context()
    print("time: ", time.time() - start)
