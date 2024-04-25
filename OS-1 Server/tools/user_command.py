import json
from enum import Enum

from pydub import AudioSegment

from base.message import Message
from core.message import MessageSenderWithRedis
from tools.bs64 import bytes2bs64
from tools.time_fmt import get_timestamp


class CommandType(Enum):
    NONE = 0
    TURN_ON = 1
    TURN_OFF = 2
    INTERRUPT = 3
    UNDER_PROCESSING = 4
    TURN_OFF_CAMERA = 5
    TURN_ON_CAMERA = 6


SPECIAL_WORDS = {
    CommandType.TURN_ON: [
        "are you there",
        "can you hear me",
        "hello",
        "你在吗",
        "在吗",
        "你好",
    ],
    CommandType.TURN_OFF: [
        "keep quiet",
        "shut up",
        "请你安静",
        "请保持安静",
    ],
    CommandType.INTERRUPT: [
        "stop",
        "停停停",
        "ok",
        "okay",
    ],
    CommandType.TURN_OFF_CAMERA: [
        "turn off your camera",
        "close your eyes",
        "关闭摄像头",
    ],
    CommandType.TURN_ON_CAMERA: [
        "turn on your camera",
        "open your eyes",
        "打开摄像头",
    ],
}


def _load_voice_file() -> dict:
    root_path = "data/voices/"
    voice_dict = json.load(open("data/voices/resp_voice.json", "r"))
    for cmd_type, voices in voice_dict.items():
        for lang, item in voices.items():
            if item["file"] == "":
                voice_dict[cmd_type][lang]["voice"] = ""
                continue
            voice_dict[cmd_type][lang]["voice"] = "data:audio/wav;base64," + bytes2bs64(
                AudioSegment.from_file(
                    open(root_path + item["file"], "rb"),
                    format=item["file"].split(".")[-1],
                    sample_width=2,
                    frame_rate=8000,
                    channels=1,
                )
                .export(format="wav")
                .read()
            )

    return voice_dict


RESP_VOICES = _load_voice_file()


class UserCommand:
    @staticmethod
    def decode_cmd(text) -> CommandType:
        text = UserCommand._clean_text(text)
        for cmd_type, cmd_list in SPECIAL_WORDS.items():
            for cmd in cmd_list:
                if text.endswith(cmd):
                    return cmd_type
        return CommandType.NONE

    @staticmethod
    def send_cmd_resp(user_id: str, cmd_type: CommandType, lang="en"):
        if cmd_type.name not in RESP_VOICES:
            return
        msg = Message(
            user_id=user_id,
            current_time=get_timestamp(),
        )
        msg.voice = RESP_VOICES[cmd_type.name][lang]["voice"]
        # msg.text = RESP_VOICES[cmd_type.name][lang]["text"]
        msg.text = f"[{cmd_type.name}]"
        MessageSenderWithRedis().send_message(msg)

    @staticmethod
    def _clean_text(text: str) -> str:
        chinese_punctuation = "（），：；｢｣、〈〉《》「」〝〞‘’“”·！？。"
        english_punctuation = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""
        text = text.lower()
        for i in chinese_punctuation + english_punctuation:
            text = text.replace(i, "")

        skip_words = ["please", "请"]
        for i in skip_words:
            text = text.replace(i, "")
        text = text.strip()
        return text


if __name__ == "__main__":
    cmd = UserCommand.decode_cmd("stop stop")
    if cmd != CommandType.NONE:
        print(cmd.name)
        UserCommand.send_cmd_resp("test1", cmd)
    # UserCommand.send_cmd_resp("test1", CommandType.TURN_OFF, lang="cn")
    # UserCommand.send_cmd_resp("test1", CommandType.INTERRUPT)
    # UserCommand.send_cmd_resp("test1", CommandType.NONE)
