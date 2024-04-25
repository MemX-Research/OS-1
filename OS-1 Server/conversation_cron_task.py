import time
import traceback
from datetime import datetime

import schedule

from base.persona import BasicPersona
from core.conversation_memorizer import MemoryGeneratorForConversationWithEvaluation
from tools.log import logger
from tools.mongo import MongoClientProxy
from tools.time_fmt import get_past_timestamp, get_timestamp


def conversation_summary_job():
    try:
        users = MongoClientProxy.get_conversation_active_users()
        if len(users) == 0:
            return
        for user_id in users:
            logger.info(f"Start conversation_summary_job for {user_id}")
            MemoryGeneratorForConversationWithEvaluation(
                user_id=user_id,
                start_time=get_past_timestamp(),
                current_time=get_timestamp(),
            ).generate_memory()
    except Exception as e:
        logger.error(
            "conversation_summary_job error: {}, {}".format(e, traceback.format_exc())
        )

def persona_refine_job():
    try:
        users = MongoClientProxy.get_conversation_active_users()
        if len(users) == 0:
            return
        for user_id in users:
            logger.info(f"Start persona_refine_job for {user_id}")
            BasicPersona(current_time=get_timestamp(), user_id=user_id).generate_task()
    except Exception as e:
        logger.error(
            "persona_refine_job error: {}, {}".format(e, traceback.format_exc())
        )

def dry_run(user_id, start_time, end_time):
    for current_time in range(start_time, end_time, 1000 * 60 * 5):
        print(datetime.fromtimestamp(current_time / 1000))
        MemoryGeneratorForConversationWithEvaluation(
            user_id=user_id, start_time=start_time, current_time=current_time
        ).generate_memory()


def service():
    schedule.every(1).minutes.do(conversation_summary_job)
    schedule.every(1).days.do(persona_refine_job)
    schedule.run_all()

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    service()


