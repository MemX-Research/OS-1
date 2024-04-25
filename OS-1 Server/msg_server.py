import asyncio
import json
import traceback
from multiprocessing import Process

from base.message import MessageSender, VoiceGenerator, Message
from base.parser import DataParser
from core.message import MessageSenderWithRedis, VoiceGeneratorWithTTS
from tools.log import logger
from tools.redis_client import RedisClientProxy
from tools.time_fmt import get_timestamp


class MessageWorker:
    def __init__(
        self,
        voice_generator: VoiceGenerator = VoiceGeneratorWithTTS(),
        message_sender: MessageSender = MessageSenderWithRedis(),
    ):
        self.voice_generator = voice_generator
        self.message_sender = message_sender
        logger.info("MessageWorker init")

    @staticmethod
    def pull_msg_text():
        data = RedisClientProxy.pop_msg_text()
        if data is None:
            return None
        return json.loads(data)

    @staticmethod
    def create_message(data):
        return Message.parse_obj(data)

    def process(self):
        while True:
            try:
                data = self.pull_msg_text()
                if data is None:
                    continue
                msg = self.create_message(data)
                start_time = get_timestamp()
                msg = self.voice_generator.generate_voice(msg)
                tts_delay = get_timestamp() - start_time
                RedisClientProxy.set_user_statistic(msg.user_id, "tts_delay", tts_delay)

                extra = None
                if msg.first_pkg:
                    extra = RedisClientProxy.get_user_statistics(msg.user_id)
                    logger.info(
                    "Send Extra Statistic info: {}, {}".format(msg.user_id, extra)
                )
                self.message_sender.send_message(msg, extra=extra)
            except Exception as e:
                logger.error(
                    "MessageWorker error: {}, {}".format(e, traceback.format_exc())
                )

    async def process_msg(self, msg, semaphore):
        async with semaphore:
            loop = asyncio.get_event_loop()

            start_time = get_timestamp()
            future = loop.run_in_executor(None, self.voice_generator.generate_voice, msg)

            msg = await future
            tts_delay = get_timestamp() - start_time
            RedisClientProxy.set_user_statistic(msg.user_id, "tts_delay", tts_delay)
            
            extra = None
            if msg.first_pkg:
                extra = RedisClientProxy.get_user_statistics(msg.user_id)
                logger.info(
                    "Send Extra Statistic info: {}, {}".format(msg.user_id, extra)
                )
            self.message_sender.send_message(msg, extra=extra)
    
    async def aprocess(self):
        user_queues = {}
        user_semaphores = {}

        while True:
            await asyncio.sleep(0.01)
            try:
                data = self.pull_msg_text()
                if data is None:
                    continue
                msg = self.create_message(data)
                userid = msg.user_id
                if userid not in user_queues:
                    # Create a new asyncio queue for this userid
                    user_queues[userid] = asyncio.Queue()
                    user_semaphores[userid] = asyncio.Semaphore(1)

                # Enqueue the data for the respective userid
                await user_queues[userid].put(msg)

                if not user_queues[userid].empty():
                    # Start asynchronous data processing for this userid
                    asyncio.create_task(self.process_msg(await user_queues[userid].get(), user_semaphores[userid]))
                
            except Exception as e:
                logger.error(
                    "MessageWorker error: {}, {}".format(e, traceback.format_exc())
                )


if __name__ == '__main__':
    # Run by thread (old version)   
    # num_workers = 1
    # thread_list = []
    # for _ in range(num_workers):
    #     thread = Process(target=MessageWorker().process)
    #     thread.start()
    #     thread_list.append(thread)
    # [thread.join() for thread in thread_list]

    # Run by asyncio
    loop = asyncio.get_event_loop()

    try:
        # Start the main loop
        loop.run_until_complete(MessageWorker().aprocess())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        pass
    finally:
        # Clean up the event loop
        loop.close()