from datetime import datetime
import time
import traceback

import schedule

from core.context_memorizer import (
    MemoryGeneratorForContext,
    MemoryGeneratorForContextWithCluster,
)
from tools.log import logger
from tools.mongo import MongoClientProxy
from tools.time_fmt import get_past_timestamp, get_timestamp


def context_summary_job():
    try:
        users = MongoClientProxy.get_context_active_users()
        if len(users) == 0:
            return
        for user_id in users:
            logger.info(f"Start context_summary_job for {user_id}")
            MemoryGeneratorForContextWithCluster(
                user_id=user_id,
                start_date=get_past_timestamp(),
                end_date=get_timestamp(),
            ).generate_memory()
    except Exception as e:
        logger.error(
            "context_summary_job error: {}, {}".format(e, traceback.format_exc())
        )


def dry_run(user_id, start_time, end_time):
    for current_time in range(start_time, end_time, 1000 * 60 * 5):
        print(datetime.fromtimestamp(current_time / 1000))
        MemoryGeneratorForContextWithCluster(
            user_id=user_id,
            start_date=get_past_timestamp(current_time=current_time),
            end_date=current_time,
        ).generate_memory()


def service():
    schedule.every(1).minutes.do(context_summary_job)
    schedule.run_all()

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    service()
