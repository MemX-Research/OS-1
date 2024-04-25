import io
import math
import wave

import matplotlib.pyplot as plt
import nemo.collections.asr as nemo_asr
import numpy as np
import torch
from PIL import Image
from nemo.core.classes import IterableDataset
from nemo.core.neural_types import NeuralType, AudioSignal, LengthsType
from torch.utils.data import DataLoader


# simple data layer to pass audio signal
class AudioDataLayer(IterableDataset):
    @property
    def output_types(self):
        return {
            "audio_signal": NeuralType(("B", "T"), AudioSignal(freq=self._sample_rate)),
            "a_sig_length": NeuralType(tuple("B"), LengthsType()),
        }

    def __init__(self, sample_rate):
        super().__init__()
        self._sample_rate = sample_rate
        self.output = True

    def __iter__(self):
        return self

    def __next__(self):
        if not self.output:
            raise StopIteration
        self.output = False
        return torch.as_tensor(self.signal, dtype=torch.float32), torch.as_tensor(
            self.signal_shape, dtype=torch.int64
        )

    def set_signal(self, signal):
        self.signal = signal.astype(np.float32) / 32768.0
        self.signal_shape = self.signal.size
        self.output = True

    def __len__(self):
        return 1


# class for streaming frame-based VAD
# 1) use reset() method to reset FrameVAD's state
# 2) call transcribe(frame) to do VAD on
#    contiguous signal's frames
# To simplify the flow, we use single threshold to binarize predictions.


class FrameVAD:
    def __init__(
        self,
        vad_model,
        model_definition,
        threshold=0.5,
        frame_len=2,
        frame_overlap=2.5,
        offset=10,
    ):
        """
        Args:
          threshold: If prob of speech is larger than threshold, classify the segment to be speech.
          frame_len: frame's duration, seconds
          frame_overlap: duration of overlaps before and after current frame, seconds
          offset: number of symbols to drop for smooth streaming
        """
        self.vad_model = vad_model
        self.vocab = list(model_definition["labels"])
        self.vocab.append("_")

        self.sr = model_definition["sample_rate"]
        self.threshold = threshold
        self.frame_len = frame_len
        self.n_frame_len = int(frame_len * self.sr)
        self.frame_overlap = frame_overlap
        self.n_frame_overlap = int(frame_overlap * self.sr)
        timestep_duration = model_definition["AudioToMFCCPreprocessor"]["window_stride"]
        for block in model_definition["JasperEncoder"]["jasper"]:
            timestep_duration *= block["stride"][0] ** block["repeat"]
        self.buffer = np.zeros(
            shape=2 * self.n_frame_overlap + self.n_frame_len, dtype=np.float32
        )
        self.offset = offset

        self.data_layer = AudioDataLayer(sample_rate=self.sr)
        self.data_loader = DataLoader(
            self.data_layer, batch_size=1, collate_fn=self.data_layer.collate_fn
        )
        self.reset()

    def _decode(self, frame, offset=0):
        assert len(frame) == self.n_frame_len
        self.buffer[: -self.n_frame_len] = self.buffer[self.n_frame_len :]
        self.buffer[-self.n_frame_len :] = frame
        logits = self.infer_signal(self.vad_model, self.buffer).cpu().numpy()[0]
        decoded = self._greedy_decoder(self.threshold, logits, self.vocab)
        return decoded

    def infer_signal(self, model, signal):
        self.data_layer.set_signal(signal)
        batch = next(iter(self.data_loader))
        audio_signal, audio_signal_len = batch
        audio_signal, audio_signal_len = audio_signal.to(
            model.device
        ), audio_signal_len.to(model.device)
        logits = model.forward(
            input_signal=audio_signal, input_signal_length=audio_signal_len
        )
        return logits

    @torch.no_grad()
    def transcribe(self, frame=None):
        if frame is None:
            frame = np.zeros(shape=self.n_frame_len, dtype=np.float32)
        if len(frame) < self.n_frame_len:
            frame = np.pad(frame, [0, self.n_frame_len - len(frame)], "constant")
        unmerged = self._decode(frame, self.offset)
        return unmerged

    def reset(self):
        """
        Reset frame_history and decoder's state
        """
        self.buffer = np.zeros(shape=self.buffer.shape, dtype=np.float32)
        self.prev_char = ""

    @staticmethod
    def _greedy_decoder(threshold, logits, vocab):
        s = []
        if logits.shape[0]:
            probs = torch.softmax(torch.as_tensor(logits), dim=-1)
            probas, _ = torch.max(probs, dim=-1)
            probas_s = probs[1].item()
            preds = 1 if probas_s >= threshold else 0
            s = [
                preds,
                str(vocab[preds]),
                probs[0].item(),
                probs[1].item(),
                str(logits),
            ]
        return s


class VoiceActivityDetector:
    def __init__(
        self,
        device: str = "cuda:2",
        step: float = 0.02,
        window_size: float = 0.31,
        pred_threshold: float = 0.5,
        judge_threshold: float = 0.4,
    ):
        self.device = device
        self.step = step
        self.window_size = window_size
        self.threshold = pred_threshold
        self.judge_threshold = judge_threshold

        self.vad_model = nemo_asr.models.EncDecClassificationModel.from_pretrained(
            "vad_marblenet"
        )
        self.cfg = self.vad_model._cfg
        self.vad_model.preprocessor = self.vad_model.from_config_dict(
            self.cfg.preprocessor
        )
        self.vad_model.eval()
        self.vad_model = self.vad_model.to(self.device)

    def inference(self, wave_file):
        wf = wave.open(wave_file, "rb")
        FRAME_LEN = self.step
        RATE = wf.getframerate()
        CHUNK_SIZE = int(FRAME_LEN * RATE)

        preds = []
        proba_b = []
        proba_s = []

        vad = FrameVAD(
            self.vad_model,
            model_definition={
                "sample_rate": RATE,
                "AudioToMFCCPreprocessor": self.cfg.preprocessor,
                "JasperEncoder": self.cfg.encoder,
                "labels": self.cfg.labels,
            },
            threshold=self.threshold,
            frame_len=self.step,
            frame_overlap=(self.window_size - self.step) / 2,
            offset=0,
        )

        data = wf.readframes(CHUNK_SIZE)

        while len(data) > 0:
            data = wf.readframes(CHUNK_SIZE)
            signal = np.frombuffer(data, dtype=np.int16)
            result = vad.transcribe(signal)

            preds.append(result[0])
            proba_b.append(result[2])
            proba_s.append(result[3])

        vad.reset()

        # results = [[self.step, self.window_size, preds, proba_b, proba_s]]
        # img = self.draw_graph(results, RATE, wave_file)

        res = self.judge(proba_s)
        return res

    def judge(self, proba_s, split=2):
        """0: silence, 1: speech
        split into n parts, if one part is speech, then the whole frame is speech
        """
        n = 3
        proba_s = np.convolve(proba_s, np.ones((n,))/n, mode="valid")
        preds = [1 if p > self.threshold else 0 for p in proba_s]

        frame_parts = np.array_split(preds, split)

        res = 0
        for frame_part in frame_parts:
            if frame_part.sum() > len(frame_part) * self.judge_threshold:
                res += 1

        if res > 0:
            return 1
        else:
            return 0

    def draw_graph(self, results, RATE, wave_file):
        """for test"""
        import librosa.display

        audio, sample_rate = librosa.load(wave_file, sr=RATE)
        dur = librosa.get_duration(y=audio, sr=sample_rate)

        plt.figure(figsize=[20, 10])

        num = len(results)
        for i in range(num):
            len_pred = len(results[i][2])
            FRAME_LEN = results[i][0]
            ax1 = plt.subplot(num + 1, 1, i + 1)

            ax1.plot(np.arange(audio.size) / sample_rate, audio, "b")
            ax1.set_xlim([-0.01, math.ceil(dur)])
            ax1.tick_params(axis="y", labelcolor="b")
            ax1.set_ylabel("Signal")
            ax1.set_ylim([-1, 1])

            proba_s = results[i][4]
            pred = [1 if p > self.threshold else 0 for p in proba_s]
            ax2 = ax1.twinx()
            ax2.plot(
                np.arange(len_pred) / (1 / results[i][0]),
                np.array(pred),
                "r",
                label="pred",
            )
            ax2.plot(
                np.arange(len_pred) / (1 / results[i][0]),
                np.array(proba_s),
                "g--",
                label="speech prob",
            )
            ax2.tick_params(axis="y", labelcolor="r")
            legend = ax2.legend(loc="lower right", shadow=True)
            ax1.set_ylabel("prediction")

            ax2.set_title(f"step {results[i][0]}s, buffer size {results[i][1]}s")
            ax2.set_ylabel("Preds and Probas")

        ax = plt.subplot(num + 1, 1, i + 2)
        S = librosa.feature.melspectrogram(
            y=audio, sr=sample_rate, n_mels=64, fmax=8000
        )
        S_dB = librosa.power_to_db(S, ref=np.max)
        librosa.display.specshow(
            S_dB, x_axis="time", y_axis="mel", sr=sample_rate, fmax=8000
        )
        ax.set_title("Mel-frequency spectrogram")
        ax.grid()
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format="png")

        im = Image.open(img_buf)
        return im


if __name__ == "__main__":
    import gradio as gr

    VAD = VoiceActivityDetector(step=0.05, window_size=0.21, pred_threshold=0.6, judge_threshold=0.5)

    inputs = [gr.components.Audio(type="filepath")]
    outputs = ["text"]

    gr.Interface(fn=VAD.inference, inputs=inputs, outputs=outputs).launch(
        server_name="0.0.0.0", server_port=7894
    )
