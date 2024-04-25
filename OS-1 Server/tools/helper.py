import io
import json
import re

import noisereduce as nr
import numpy as np
from pydub import AudioSegment
from pydub import silence

from tools.vad_api import ASRVoiceActivityAPI

SPEECH_RECOGNITION_BLACKLIST = [
    "you",
    "Bye.",
    "Bye!",
    "Okay.",
    "So.",
    ".",
    "Thank you.",
    "Thanks.",
    "Yeah.",
    "Peace.",
    "pfft",
    "pffft",
    "?",
    "Hmm.",
    "I",
]


class TextHelper:
    @staticmethod
    def remove_non_text(text: str):
        text = text.replace("\n", "").strip('"“”')
        return text

    @staticmethod
    def remove_img_prefix(text: str):
        text = (
            text.replace("Assistant:", "")
            .replace("Human:", "")
            .replace("The image features", "")
            .replace("The image depicts", "")
            .replace("The image captures", "")
            .replace("The image shows", "")
            .replace("The image is", "")
            .replace("In the image", "")
            .strip()
            .replace("\n", " ")
        )
        return text

    @staticmethod
    def is_text(token: str) -> bool:
        txt = re.search(
            r"^[\u4e00-\u9fa5a-zA-Z0-9',\"\-\s]+$",
            token,
        )
        return txt is not None

    @staticmethod
    def is_speech(token: str) -> bool:
        txt = re.search(
            r"^[\u4e00-\u9fa5a-zA-Z0-9'\-\s，。！？,.?!]+$",
            token,
        )
        return txt is not None and token not in SPEECH_RECOGNITION_BLACKLIST

    @staticmethod
    def is_english(token: str) -> bool:
        txt = re.search(
            r"^[a-zA-Z0-9'\"\-\s,.?!:;]+$",
            token,
        )
        return txt is not None

    @staticmethod
    def parse_json(json_str: str) -> dict:
        json_str = "".join(json_str.partition("{")[1:])
        json_str = json_str.split("\n\n")[0]
        if "}" not in json_str:
            json_str += "}"
        json_str = "".join(json_str.rpartition("}")[:-1])

        json_str = json_str.strip("\n")

        json_obj = json.loads(json_str)

        return json_obj


class VoiceHelper:
    @staticmethod
    def _is_silent(
        audio_segment: AudioSegment, silence_thresh=-45, min_silence_len=100
    ) -> bool:
        if audio_segment is None:
            return True
        nonsilent_segment = silence.detect_nonsilent(
            audio_segment,
            silence_thresh=silence_thresh,
            min_silence_len=min_silence_len,
        )
        return len(nonsilent_segment) == 0

    @classmethod
    def is_silent(
        cls, audio_segment: AudioSegment, silence_thresh=-45, min_silence_len=100
    ) -> bool:
        if cls._is_silent(
            audio_segment,
            silence_thresh=silence_thresh,
            min_silence_len=min_silence_len,
        ):
            return True
        wav_buf = io.BytesIO()
        audio_segment.export(wav_buf, format="wav")
        return not ASRVoiceActivityAPI.is_voice(wav_buf.getvalue())

    @staticmethod
    def bytes2audio(wav_bytes: bytes):
        audio = AudioSegment.from_wav(io.BytesIO(wav_bytes))
        audio = AudioSegment(
            nr.reduce_noise(
                np.array(audio.get_array_of_samples()), sr=audio.frame_rate
            ).tobytes(),
            frame_rate=audio.frame_rate,
            sample_width=audio.sample_width,
            channels=audio.channels,
        )
        return audio
