from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Optional

from base.prompt import Context


@dataclass
class Response:
    context: Optional[Context] = None
    prompt: Optional[str] = None
    reply: Optional[str] = None


class ResponseGenerator(metaclass=ABCMeta):
    @abstractmethod
    def generate_response(self, prompt: Context) -> Response:
        pass
