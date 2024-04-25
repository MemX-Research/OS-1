from multiprocessing import Queue
from threading import Thread
from typing import Optional

from base.auditory import AuditoryPerceptron, AuditoryAudio, AuditoryContext
from tools.asr_api import RealTimeWhisperWithSilenceDetection
from tools.time_fmt import get_timestamp


class AuditoryContextRecognizer(AuditoryPerceptron):
    def __init__(self):
        self.audio_processor = RealTimeWhisperWithSilenceDetection()
        self.audio_queue = Queue()
        self.last_word_time = get_timestamp()

        def wait_for_audio():
            result = self.audio_processor.audio2text()
            self.audio_queue.put(result)

        Thread(target=wait_for_audio).start()

    def transcript_text(self, audio: AuditoryAudio) -> Optional[AuditoryContext]:
        if self.audio_queue.empty():
            if self.audio_processor.record(audio.audio_data):
                self.last_word_time = audio.current_time
            return
        text, full_audio = audio_queue.get()
        return AuditoryContext(
            current_time=self.last_word_time,
            user_id=audio.user_id,
            user_audio=full_audio,
            user_text=text,
        )


if __name__ == "__main__":
    import io
    from pydub import AudioSegment
    import time

    start_time = time.time()
    audio_recognizer = AuditoryContextRecognizer()
    for i in range(5):
        audio_data = f"../data/audios/zh_{i}.mp3"
        sound = AudioSegment.from_file(audio_data, format="mp3")
        output = io.BytesIO()
        sound.export(output, format="wav")
        wav_data = AudioSegment.from_wav(output)
        res = audio_recognizer.transcript_text(
            AuditoryAudio(
                user_id="test", audio_data=wav_data, current_time=get_timestamp()
            )
        )
        if res is not None:
            print(res)
    print(time.time() - start_time)
