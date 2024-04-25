from abc import ABCMeta, abstractmethod
from typing import Optional

from pydub import AudioSegment

from base.tag import Tag


class AuditoryAudio(Tag):
    audio_data: AudioSegment = None


class AuditoryContext(Tag):
    user_audio: Optional[str] = None
    user_text: Optional[str] = None


class AuditoryPerceptron(metaclass=ABCMeta):
    @abstractmethod
    def transcript_text(self, audio: AuditoryAudio) -> Optional[AuditoryContext]:
        pass
