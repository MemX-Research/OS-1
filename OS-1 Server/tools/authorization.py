import traceback
from typing import Optional

import uuid
import bcrypt
from cryptography.fernet import Fernet
from pydantic import BaseModel

from templates.custom_prompt import DEFAULT_SYS_PROMPT
from tools.log import logger
from tools.mongo import MongoClientProxy
from tools.time_fmt import get_timestamp


class User(BaseModel):
    user_id: Optional[str]
    hashed_pwd: Optional[bytes]
    secret_key: Optional[bytes]
    created_time: Optional[int]
    last_login_time: Optional[int]
    system_prompt: Optional[str]
    current_promptid: Optional[str]
    
    def encrypt_msg(self, msg: str) -> str:
        cipher_suite = Fernet(self.secret_key)
        return cipher_suite.encrypt(msg.encode("utf-8")).decode("utf-8")

    def decrypt_msg(self, encrypted_msg: str) -> str:
        if self.secret_key is None or encrypted_msg == "":
            return encrypted_msg
        cipher_suite = Fernet(self.secret_key)
        return cipher_suite.decrypt(encrypted_msg.encode("utf-8")).decode("utf-8")

class User_prompt(BaseModel):
    prompt_id: Optional[str]
    user_id: Optional[str]
    title: Optional[str]
    content: Optional[str]

class PromptController:
    collection = MongoClientProxy.get_collection("prompt") 
    
    def add_prompt(self, user_id: str, title: str, content: str):
        existing_prompt = self.collection.find_one({"title": title})
        if existing_prompt:
            self.collection.delete_one({"title": title})
    
        new_prompt = User_prompt(
            prompt_id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            content=content
        )
        self.collection.insert_one(new_prompt.dict())
        return user_id, title, content
    
class UserController:
    collection = MongoClientProxy.get_collection("user")
    
    def init_collection(self):
        self.collection.create_index("user_id", unique=True)

    def add_user(self, user_id: str, password: str) -> bool:
        """password: plain text"""
        password = password.encode("utf-8")
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
        try:
            user = self.get_user(user_id)
            if user is not None:
                return False
            new_user = User(
                user_id=user_id,
                hashed_pwd=hashed_password,
                secret_key=Fernet.generate_key(),
                created_time=get_timestamp(),
                last_login_time=get_timestamp(),
                system_prompt=DEFAULT_SYS_PROMPT,
            )
            self.collection.insert_one(new_user.dict())
        except Exception as e:
            logger.error("UserController add_user error: {}".format(e))
            return False
        return True

    def update_user(self, user_id, **kwargs) -> bool:
        try:
            res = self.collection.update_one({"user_id": user_id}, {"$set": kwargs})
            if res.modified_count == 0:
                return False
        except Exception as e:
            logger.error(
                "UserController update_user error: {}, {}".format(
                    e, traceback.format_exc()
                )
            )
            return False
        return True

    def update_password(self, user_id: str, password: str) -> bool:
        password = password.encode("utf-8")
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

        ret = self.update_user(user_id, hashed_pwd=hashed_password)
        if ret:
            print("update password success")
            print(f"new password `{user_id}`: ", hashed_password)
        else:
            print("update password failed")
        return ret

    def update_last_login_time(self, user_id):
        return self.update_user(user_id, last_login_time=get_timestamp())

    def get_user(self, user_id) -> User:
        res = self.collection.find_one({"user_id": user_id})
        if res is None:
            return None
        return User.parse_obj(res)

    def check_password(self, user_id, password) -> bool:
        password = password.encode("utf-8")
        user = self.get_user(user_id)
        if user is None:
            return False
        return bcrypt.checkpw(password, user.hashed_pwd)

    def get_all_users(self):
        user_ids = self.collection.distinct("user_id")
        return user_ids

    def _reset_all_prompt(self):
        user_ids = self.get_all_users()
        for user_id in user_ids:
            self.update_user(user_id, system_prompt=DEFAULT_SYS_PROMPT)
    
        
        
        
if __name__ == "__main__":
    userController = UserController()
    # userController.init_collection()
    # ret = userController.add_user("admin", "admin")
    # if userController.check_password("admin", "admin"):
    #     print("check password success")
    #     user = userController.get_user("admin")
    #     encrypted_msg = user.encrypt_msg("hello")
    #     print(encrypted_msg)
    #     print(user.decrypt_msg(encrypted_msg))
    # else:
    #     print("check password failed")

    # userController.update_password("test1", "123456")

    # userController._reset_all_prompt()
