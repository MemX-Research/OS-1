from base.conversation import Conversation
from templates.response import CHAT_SYSTEM_PROMPT
from tools.authorization import UserController, User
from tools.bs64 import bs642bytes
from tools.mongo import MongoClientProxy
from tools.time_fmt import timestamp_to_str, str_to_timestamp, get_past_timestamp
from datetime import datetime, timedelta


def get_conversation_statistics(user_id: str, start_time: int, end_time: int):
    start_date = datetime.fromtimestamp(start_time / 1000)
    end_date = datetime.fromtimestamp(end_time / 1000)

    day_statistics = {
        "date": [],
        "rounds": [],
        "minutes": [],
        "sessions": [],
    }
    hour_statistics = {
        "hour": list(range(24)),
        "avg_rounds": [0] * 24,
    }
    all_hour_rounds = []

    current_date = start_date
    while current_date <= end_date:
        day_start = int(
            current_date.replace(hour=0, minute=0, second=0).timestamp() * 1000
        )
        day_end = day_start + 24 * 60 * 60 * 1000

        convs = Conversation.get_conversation_by_duration(
            user_id, day_start, day_end, limit=0
        )
        day_statistics["date"].append(current_date.strftime("%Y-%m-%d"))
        # 1. 统计全天对话轮数
        day_statistics["rounds"].append(len(convs))

        # 2. 统计每个小时对话的轮数
        if len(convs) > 0:
            hour_rounds = [0] * 24
            for conv in convs:
                hour_rounds[
                    datetime.fromtimestamp(conv["current_time"] / 1000).hour
                ] += 1
            all_hour_rounds.append(hour_rounds)

        # 3. 统计使用时间、session数量，每条对话之后的 SESSION_INTERVAL 分钟算作活动时间
        SESSION_INTERVAL = 3 * 60 * 1000
        duration = 0  # ms
        sessions = 0
        if len(convs) > 0:
            cur_start = convs[0]["current_time"]
            cur_end = cur_start + SESSION_INTERVAL
            for conv in convs[1:]:
                if conv["current_time"] < cur_end:
                    cur_end = conv["current_time"] + SESSION_INTERVAL
                else:
                    duration += cur_end - cur_start
                    sessions += 1
                    cur_start = conv["current_time"]
                    cur_end = cur_start + SESSION_INTERVAL

            duration += cur_end - cur_start
            sessions += 1
        day_statistics["minutes"].append(duration / 1000 / 60)
        day_statistics["sessions"].append(sessions)

        current_date += timedelta(days=1)

    if len(all_hour_rounds) > 0:
        hour_statistics["avg_rounds"] = [sum(x) / len(x) for x in zip(*all_hour_rounds)]
    return day_statistics, hour_statistics


if __name__ == "__main__":
    day_statistics, hour_statistics = get_conversation_statistics(
        "test1", get_past_timestamp(7, day_start_hour=0), get_past_timestamp()
    )
    print(day_statistics, hour_statistics)
