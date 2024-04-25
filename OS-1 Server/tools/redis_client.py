from enum import Enum

import redis


class UserStatus(Enum):
    OFF = 0
    IDLE = 1
    UNDER_PROCESSING = 2
    INTERRUPT = 3


class RedisClient:
    def __init__(self, host="localhost", port=6379, db=2):
        self.redis_client = redis.StrictRedis(host=host, port=port, db=db)

    def get_client(self):
        return self.redis_client

    def rpush(self, key, value):
        self.redis_client.rpush(key, value)

    def lpop(self, key):
        return self.redis_client.lpop(key)

    def sadd(self, key, value):
        self.redis_client.sadd(key, value)

    def srem(self, key, value):
        self.redis_client.srem(key, value)

    def keys(self, pattern):
        return self.redis_client.keys(pattern)

    def smembers(self, key):
        return self.redis_client.smembers(key)

    def set(self, key, value, timeout=None):
        self.redis_client.set(key, value)
        if timeout:
            self.redis_client.expire(key, timeout)

    def get(self, key):
        return self.redis_client.get(key)

    def push_data(self, uid, data):
        self.rpush(f"data_{uid}", data)

    def pop_data(self, uid):
        return self.lpop(f"data_{uid}")

    def push_image_data(self, data):
        self.rpush("input_image", data)

    def pop_image_data(self):
        return self.lpop("input_image")

    def push_audio_data(self, uid, data):
        self.rpush(f"input_audio_{uid}", data)

    def insert_audio_data(self, uid, data):
        self.lpush(f"input_audio_{uid}", data)

    def pop_audio_data(self, uid):
        return self.lpop(f"input_audio_{uid}")

    def push_text_data(self, data):
        self.rpush("input_text", data)

    def pop_text_data(self):
        return self.lpop("input_text")

    def push_msg_text(self, data):
        self.rpush("response_text", data)

    def pop_msg_text(self):
        return self.lpop("response_text")

    def push_msg(self, uid, data, timeout=900):
        key = f"response_{uid}"
        self.rpush(key, data)
        if timeout:
            self.redis_client.expire(key, timeout)

    def pop_msg(self, uid):
        return self.lpop(f"response_{uid}")

    def add_user(self, uid):
        self.sadd("users", uid)

    def del_user(self, uid):
        self.srem("users", uid)

    def get_users(self):
        return [str(user, encoding="utf-8") for user in self.smembers("users")]

    def set_latest_active_ts(self, uid, timestamp, timeout=180):
        self.set(f"latest_active_ts_{uid}", timestamp, timeout=timeout)

    def get_latest_active_ts(self, uid):
        return self.get(f"latest_active_ts_{uid}")

    def get_active_users(self):
        res = self.keys("active_*")
        res = ["".join(x.decode("utf-8").split("_")[1:]) for x in res]
        return res

    def set_active_user(self, user_id: str, timeout_secs=600):
        timestamp = int(time.time() * 1000)
        self.set(f"active_{user_id}", timestamp, timeout=timeout_secs)

    def set_user_status(self, user_id: str, status: UserStatus, timeout=None):
        """`status` 0: off, 1: idle, 2: under processing, 3: interrupt"""
        if status == UserStatus.INTERRUPT:
            timeout = 2
        self.set(f"status_{user_id}", status.value, timeout=timeout)

    def get_user_status(self, user_id: str) -> UserStatus:
        """`status` 0: off, 1: idle, 2: under processing, 3: interrupt"""
        status = self.get(f"status_{user_id}")
        status = 1 if status is None else int(status)
        return UserStatus(status)

    def set_user_statistic(self, user_id: str, key: str, value: str, timeout=None):
        self.set(f"statistic${user_id}${key}", value, timeout=timeout)

    def get_user_statistics(self, user_id: str) -> dict:
        keys = self.keys(f"statistic${user_id}$*")
        res = {}
        for key in keys:
            key = key.decode("utf-8")
            value = self.get(key)
            res[key.split("$")[-1]] = value.decode("utf-8")
        return res

    def set_reset_token(self, user_id: str, token: str, timeout=300):
        self.set(f"reset_token${user_id}", token, timeout=timeout)

    def get_reset_token(self, user_id: str):
        res = self.get(f"reset_token${user_id}")
        return res.decode("utf-8") if res else None

    def del_reset_token(self, user_id: str):
        self.redis_client.delete(f"reset_token${user_id}")


RedisClientProxy = RedisClient()

if __name__ == "__main__":
    from base.auditory import AuditoryContext
    from tools.time_fmt import get_timestamp

    voice = AuditoryContext(
        current_time=get_timestamp(),
        user_id="test",
        user_text="I have doubts about my own abilities, and I feel confused about the path ahead.",
        # user_text="I do not want to play word game now",
        # user_text="I'm really worried about being able to do research well.",
        # user_text="it's tough.",
        # user_text="I was overwhelmed with the research.",
        # user_text="I'm in a bad mood, and I don't want to think about how to solve this problem",
        # user_text="I have encountered some challenges. ",
        # user_text="All right, it is boring.",
        # user_text="You're really bad at comforting people",
        # user_text="I finds it hard to make progress in the research.",
    )
    RedisClientProxy.push_text_data(voice.json())

    # import time
    # import sys
    #
    # sys.path.append("..")
    # from base.auditory import AuditoryContext
    # from tools.time_fmt import get_timestamp
    #
    # RedisClientProxy.set_user_status("test_zyxu", UserStatus.IDLE)
    # # RedisClientProxy.set_latest_active_ts("test", "123")
    # # print(RedisClientProxy.get_latest_active_ts("test"))
    # # time.sleep(61)
    # # print(RedisClientProxy.get_latest_active_ts("test"))
    # # print(RedisClientProxy.get_user_status("test1"))
    # for i in range(15):
    #     voice = AuditoryContext(
    #         current_time=get_timestamp(),
    #         user_id="test_zyxu",
    #         # user_text="hey samantha",
    #         user_text="Oh godness I can't hear you",
    #         # user_text="你最喜欢的歌手是谁？",
    #         # user_text="keep quiet",
    #     )
    #     RedisClientProxy.push_text_data(voice.json())
    #     time.sleep(1)
