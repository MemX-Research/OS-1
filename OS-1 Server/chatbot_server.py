import json
import time
import traceback
from multiprocessing import Process

from base.conversation import Conversation
from base.parser import DataParser
from base.prompt import Context
from base.prompt import PromptGenerator
from base.response import ResponseGenerator
from core.message import MessageSenderWithRedis, Message
from core.prompt import PromptGeneratorWithAgent
from core.response import ResponseGeneratorWithGPT4
from tools.helper import TextHelper
from tools.log import logger
from tools.redis_client import RedisClientProxy, UserStatus
from tools.time_fmt import get_timestamp
from tools.user_command import CommandType, UserCommand


class ChatbotWorker:
    def __init__(
        self,
        # prompt_generator: PromptGenerator = PromptGeneratorWithHistory(),
        prompt_generator: PromptGenerator = PromptGeneratorWithAgent(),
        response_generator: ResponseGenerator = ResponseGeneratorWithGPT4(),
        # response_generator: ResponseGenerator = ResponseGeneratorWithLLama(),
    ):
        self.prompt_generator = prompt_generator
        self.response_generator = response_generator
        logger.info("ChatbotWorker init")

    @staticmethod
    def pull_text():
        data = RedisClientProxy.pop_text_data()
        if data is None:
            return None
        return json.loads(data)

    def process(self):
        while True:
            try:
                # === 1. Fetch Data ===
                data = self.pull_text()
                if data is None:
                    continue

                context = Context(
                    current_time=DataParser.parse_time(data),
                    user_id=DataParser.parse_uid(data),
                    user_text=DataParser.parse_text(data),
                    user_audio=DataParser.parse_audio(data),
                )
                # only process english text
                if TextHelper.is_english(context.user_text) is False:
                    continue

                # === 2. Judge User Command ===
                is_cmd = self.process_command(
                    user_id=context.user_id, user_text=context.user_text
                )
                if is_cmd:
                    continue

                # === 3. Check User Status ===
                user_status = RedisClientProxy.get_user_status(context.user_id)
                if user_status == UserStatus.UNDER_PROCESSING:
                    logger.info(
                        f"user `{context.user_id}` is processing, discarding message '{context.user_text}'"
                    )
                    continue
                if user_status == UserStatus.OFF or user_status == UserStatus.INTERRUPT:
                    continue

                # === 4. Generate Prompt ===
                RedisClientProxy.set_latest_active_ts(
                    context.user_id, context.current_time
                )
                RedisClientProxy.set_user_status(
                    context.user_id, UserStatus.UNDER_PROCESSING, timeout=60
                )
                UserCommand.send_cmd_resp(context.user_id, CommandType.UNDER_PROCESSING)

                logger.info(
                    f"processing message '{context.user_text}' for user: {context.user_id}"
                )

                # Return the ASR result to client
                MessageSenderWithRedis().send_message(
                    Message(
                        user_id=context.user_id,
                        current_time=get_timestamp(),
                        text="<User>: {}".format(context.user_text.strip()),
                        voice="",
                    )
                )
                start_time = get_timestamp()
                context = self.prompt_generator.generate_prompt(context)
                prompt_delay = get_timestamp() - start_time
                RedisClientProxy.set_user_statistic(
                    context.user_id, "prompt_delay", prompt_delay
                )
                logger.info(
                    "Prompt with {} in {}, response cost: {:.2f}s".format(
                        context.user_id,
                        context.current_time,
                        prompt_delay / 1000,
                    )
                )

                # === 5. Generate Response ===
                res = self.response_generator.generate_response(context)

                user_status = RedisClientProxy.get_user_status(context.user_id)
                if user_status == UserStatus.UNDER_PROCESSING:
                    RedisClientProxy.set_user_status(context.user_id, UserStatus.IDLE)

                # === 6. Save Conversation ===
                if res is None:
                    continue

                if res.reply == "":
                    continue

                Conversation(
                    current_time=res.context.current_time,
                    user_id=res.context.user_id,
                    human=res.context.user_text,
                    ai=res.reply,
                    context_id=res.context.context_id,
                    history_id=res.context.history_id,
                    audio=res.context.user_audio,
                    prompt=res.prompt,
                ).save_conversation()

                logger.info(
                    "Chat with {} in {}, response cost: {:.2f}s, Response: {}".format(
                        res.context.user_id,
                        res.context.current_time,
                        time.time() - res.context.current_time / 1000,
                        res.reply,
                    )
                )

                # === 7. Generate Profile ===
                # history_generator = ProfileHistoryGenerator(user_id=res.context.user_id)
                # Thread(target=history_generator.generate_history).start()

            except Exception as e:
                logger.error(
                    "ChatbotWorker error: {}, {}".format(e, traceback.format_exc())
                )

    def process_command(self, user_text: str, user_id: str) -> bool:
        cmd = UserCommand.decode_cmd(user_text)

        if cmd == CommandType.TURN_ON:
            RedisClientProxy.set_user_status(user_id, UserStatus.IDLE)
        elif cmd == CommandType.TURN_OFF:
            RedisClientProxy.set_user_status(user_id, UserStatus.OFF)
        elif cmd == CommandType.INTERRUPT:
            # only set interrupt flag when chatbot is under processing
            if RedisClientProxy.get_user_status(user_id) == UserStatus.UNDER_PROCESSING:
                print("set interrupt")
                RedisClientProxy.set_user_status(user_id, UserStatus.INTERRUPT)
        else:
            return False
        logger.info("User {} command: {}".format(user_id, cmd.name))
        UserCommand.send_cmd_resp(user_id, cmd)
        return True


num_workers = 3
thread_list = []
for _ in range(num_workers):
    thread = Process(target=ChatbotWorker().process)
    thread.start()
    thread_list.append(thread)
[thread.join() for thread in thread_list]
