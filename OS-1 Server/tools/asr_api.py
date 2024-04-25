import io
import time
from datetime import datetime, timedelta
from multiprocessing import Queue
from tempfile import NamedTemporaryFile

import requests
import speech_recognition as sr
from pydub import AudioSegment

from tools.asr_ali_nls import ASRAPITool
from tools.bs64 import bytes2bs64
from tools.helper import VoiceHelper
from tools.log import logger


class WhisperAPI:
    def __init__(self, url="http://127.0.0.1:7890"):
        self.base_url = url + "/run/predict"
        logger.info("Initializing Whisper via %s" % url)

    def inference(self, audio_bytes: bytes) -> str:
        pcm_data = AudioSegment.from_file(
            io.BytesIO(audio_bytes),
            format="wav",
        )
        pcm_data.export(out_f="test.wav", format="wav")

        base64_str = bytes2bs64(audio_bytes)
        data = {
            "data": [
                {"name": "audio.wav", "data": f"data:audio/wav;base64,{base64_str}"},
            ]
        }
        response = requests.post(self.base_url, json=data).json()
        logger.info("whisper api: {}".format(response))
        return response["data"][0]


ASRWhisperAPI = WhisperAPI()


class RealTimeWhisper:
    def __init__(
        self,
        energy_threshold=1000,
        phrase_timeout=3,
    ):
        self.data_queue = Queue()
        self.recorder = sr.Recognizer()
        self.recorder.energy_threshold = energy_threshold
        self.phrase_timeout = phrase_timeout
        self.sample_rate = None
        self.sample_width = None

    def listen(self) -> bool:
        return not self.data_queue.empty()

    def record(self, mp3_data: AudioSegment) -> None:
        def record_callback(audio: sr.AudioData) -> None:
            data = audio.get_raw_data()
            self.data_queue.put(data)
            print("recording...")

        wav_path = NamedTemporaryFile(suffix="wav").name
        mp3_data.export(wav_path, format="wav")

        with sr.AudioFile(wav_path) as source:
            audio = self.recorder.record(source)
            record_callback(audio)
            self.sample_rate = source.SAMPLE_RATE
            self.sample_width = source.SAMPLE_WIDTH

    def audio2text(self) -> (str, bytes):
        full_audio = bytes()
        phrase_time = datetime.utcnow()
        while True:
            while self.listen():
                print("listening...")
                # This is the last time we received new audio data from the queue.
                phrase_time = datetime.utcnow()
                # Pull raw recorded audio from the queue.
                data = self.data_queue.get()
                # Concatenate our current audio data with the latest audio data.
                full_audio += data

            # If enough time has passed between recordings, consider the phrase complete.
            now = datetime.utcnow()
            if (
                now - phrase_time > timedelta(seconds=self.phrase_timeout)
                and not self.listen()
            ):
                break

        audio_data = sr.AudioData(
            full_audio, self.sample_rate, self.sample_width
        ).get_wav_data()

        start_time = time.time()
        text = ASRWhisperAPI.inference(audio_data)
        print("whisper api, 耗时: {:.2f}秒".format(time.time() - start_time))

        return text, audio_data


class RealTimeWhisperWithSilenceDetection:
    def __init__(
        self,
        energy_threshold=1000,
        adjust_for_ambient_noise=False,
        phrase_timeout_seconds=3,
        wait_silence_phrase=1,
        max_phrase_number=15,
    ):
        self.data_queue = Queue()
        self.recorder = sr.Recognizer()
        self.recorder.energy_threshold = energy_threshold
        self.adjust_for_ambient_noise = adjust_for_ambient_noise
        self.phrase_timeout_seconds = phrase_timeout_seconds
        self.wait_silence_phrase = wait_silence_phrase
        self.max_phrase_number = max_phrase_number
        self.silence_phrase_number = 0
        self.total_phrase_number = 0
        self.sample_rate = 16000
        self.sample_width = 2

    def listen(self) -> bool:
        return not self.data_queue.empty()

    def is_silent(self, audio_segment: AudioSegment) -> bool:
        return VoiceHelper.is_silent(audio_segment)

    def record(self, audio_segment: AudioSegment) -> bool:
        if self.is_silent(audio_segment):
            self.silence_phrase_number += 1
            return False
        wav_path = NamedTemporaryFile(suffix="wav").name
        audio_segment.export(wav_path, format="wav")
        with sr.AudioFile(wav_path) as source:
            if self.adjust_for_ambient_noise:
                self.recorder.adjust_for_ambient_noise(source)
            if source.SAMPLE_RATE is not None:
                self.sample_rate = source.SAMPLE_RATE
            if source.SAMPLE_WIDTH is not None:
                self.sample_width = source.SAMPLE_WIDTH
            audio_data = self.recorder.record(source)
            self.data_queue.put(audio_data.get_raw_data())
        self.total_phrase_number += 1
        logger.info("recording...")
        return True

    def audio2text(self) -> (str, bytes):
        full_audio = bytes()
        phrase_time = datetime.utcnow()
        while True:
            while self.listen():
                logger.info("listening...")
                # This is the last time we received new audio data from the queue.
                phrase_time = datetime.utcnow()
                # Pull raw recorded audio from the queue.
                data = self.data_queue.get()
                # Concatenate our current audio data with the latest audio data.
                full_audio += data

            if (
                self.silence_phrase_number >= self.wait_silence_phrase
                or self.total_phrase_number >= self.max_phrase_number
            ) and not self.listen():
                break

            # If enough time has passed between recordings, consider the phrase complete.
            now = datetime.utcnow()
            if (
                now - phrase_time > timedelta(seconds=self.phrase_timeout_seconds)
                and not self.listen()
            ):
                break

        audio_data = sr.AudioData(
            full_audio, self.sample_rate, self.sample_width
        ).get_wav_data()

        # text = ASRWhisperAPI.inference(audio_data)
        # text = opencc.OpenCC().convert(text)
        text = ASRAPITool.inference(audio_data)

        return text, audio_data


if __name__ == "__main__":

    audio_processor = RealTimeWhisperWithSilenceDetection()
    for i in range(5):
        audio_data = f"../data/audios/zh_{i}.mp3"
        sound = AudioSegment.from_file(audio_data, format="mp3")
        output = io.BytesIO()
        sound.export(output, format="wav")
        wav_data = AudioSegment.from_wav(output)
        audio_processor.record(wav_data)
        # res = audio_processor.is_voice(wav_data)
        # print(f"res: {res}")
    text, _ = audio_processor.audio2text()
    print(text)
