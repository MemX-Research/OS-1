import json

from base.active import ActiveSpeaker
from base.auditory import AuditoryContext
from base.visual import VisualContext
from tools.log import logger
from tools.redis_client import RedisClientProxy, UserStatus
from tools.similarity import is_texts_similar
from tools.time_fmt import get_timestamp


class ActiveSpeakerWithAttention(ActiveSpeaker):
    def __init__(self, user_id):
        self.user_id = user_id

    @staticmethod
    def judge_attention_similarity(
        user_id: str, similarity_threshold=0.8, similarity_ratio=0.6
    ) -> bool:
        res = VisualContext.get_latest_context(user_id, seconds=180, limit=10)
        caption_list = [item["attention"] for item in res]
        logger.info("caption list {}: {}".format(len(caption_list), caption_list))
        if len(caption_list) < 5:
            logger.info("not enough context for {}".format(user_id))
            return False
        return is_texts_similar(caption_list, similarity_threshold, similarity_ratio)

    def active_conversation(self):
        if RedisClientProxy.get_user_status(self.user_id) != UserStatus.IDLE:
            return
        if RedisClientProxy.get_latest_active_ts(self.user_id) is not None:
            logger.info("active conversation limit for {}".format(self.user_id))
            return

        if not self.judge_attention_similarity(self.user_id):
            logger.info("not active conversation for {}".format(self.user_id))
            return None

        logger.info("active conversation for {}".format(self.user_id))

        voice = AuditoryContext(
            current_time=get_timestamp(),
            user_id=self.user_id,
            user_text="(No response)",
            user_audio=bytes(),
        )

        RedisClientProxy.push_text_data(json.dumps(voice.dict()))

        RedisClientProxy.set_latest_active_ts(self.user_id, voice.current_time)
