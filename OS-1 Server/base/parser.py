import io

from PIL import Image
from pydub import AudioSegment

from tools.bs64 import bs642bytes
from tools.helper import VoiceHelper


class DataParser:
    @staticmethod
    def parse_time(data: dict):
        return data["current_time"]

    @staticmethod
    def parse_uid(data: dict):
        return data["user_id"]

    @staticmethod
    def parse_gaze(data: dict):
        gazes = sorted(data["gazes"], key=lambda x: x["confidence"])
        if len(gazes) == 0:
            return None
        return gazes[-1]["norm_pos_x"], gazes[-1]["norm_pos_y"]

    @staticmethod
    def parse_image(data: dict):
        if data["scene_bytes"] == "":
            return None
        scene_bytes = bs642bytes(data["scene_bytes"])
        scene_image = Image.open(io.BytesIO(scene_bytes)).rotate(angle=270, expand=True)
        return scene_image

    @staticmethod
    def parse_voice(data: dict):
        if data["voice_bytes"] == "":
            return None
        voice_bytes = bs642bytes(data["voice_bytes"])
        pcm_data = AudioSegment.from_file(
            io.BytesIO(voice_bytes),
            sample_width=2,
            frame_rate=16000,
            channels=1,
            format="pcm",
        )
        wav_data = pcm_data.export(format="wav").read()
        return VoiceHelper.bytes2audio(wav_data)

    @staticmethod
    def parse_voice_bytes(data: dict):
        if data["voice_bytes"] == "":
            return None
        return bs642bytes(data["voice_bytes"])

    @staticmethod
    def parse_text(data: dict):
        return data["user_text"]

    @staticmethod
    def parse_audio(data: dict):
        return data["user_audio"]

    @staticmethod
    def parse_msg_text(data: dict):
        return data["text"]

    @staticmethod
    def parse_emotion(data: dict):
        return data["emotion"]
