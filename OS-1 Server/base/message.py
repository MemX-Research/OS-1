from abc import ABCMeta, abstractmethod
from typing import Optional

from base.tag import Tag


class Message(Tag):
    text: Optional[str] = None
    voice: Optional[str] = None
    emotion: Optional[str] = None
    first_pkg: bool = False
    start_time: Optional[int] = None


class VoiceGenerator(metaclass=ABCMeta):
    @abstractmethod
    def generate_voice(self, msg: Message) -> Optional[Message]:
        pass


class MessageSender(metaclass=ABCMeta):
    @abstractmethod
    def send_message(self, msg: Message, **kwargs):
        pass
