from abc import ABCMeta, abstractmethod


class ActiveSpeaker(metaclass=ABCMeta):
    @abstractmethod
    def active_conversation(self):
        pass
