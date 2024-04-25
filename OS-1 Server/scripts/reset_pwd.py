import uuid
import sys

sys.path.append("..")
sys.path.append(".")
from tools.authorization import UserController
from tools.redis_client import RedisClientProxy


def generate_reset_token(user_id: str, timeout=3600) -> str:
    """Generate reset token for user"""
    token = str(uuid.uuid4())
    RedisClientProxy.set_reset_token(user_id, token, timeout=timeout)
    return token


if __name__ == "__main__":
    minutes = 60

    user_id = input("Input the user_id to be reset: ")
    user = UserController().get_user(user_id)
    if user is None:
        print("User not found.")
        exit(0)
    token = generate_reset_token(user_id, timeout=minutes * 60)
    print("Token:", token)
    print(f"Token will be expired in {minutes} minutes.")
