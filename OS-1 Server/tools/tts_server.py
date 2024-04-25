import io
import os
from typing import Union

import numpy as np
import paddle
import yaml
from paddlespeech.cli.tts.infer import TTSExecutor
from paddlespeech.t2s.frontend.zh_frontend import Frontend
from paddlespeech.t2s.models.fastspeech2 import FastSpeech2
from paddlespeech.t2s.models.fastspeech2 import FastSpeech2Inference
from paddlespeech.t2s.models.parallel_wavegan import PWGGenerator
from paddlespeech.t2s.models.parallel_wavegan import PWGInference
from paddlespeech.t2s.modules.normalizer import ZScore
from scipy.io.wavfile import write
from yacs.config import CfgNode

from bs64 import bytes2bs64

fastspeech2_config_path = (
    "/home/hlxu/download/fastspeech2_nosil_baker_ckpt_0.4/default.yaml"
)
fastspeech2_checkpoint_path = (
    "/home/hlxu/download/fastspeech2_nosil_baker_ckpt_0.4/snapshot_iter_76000.pdz"
)
fastspeech2_stat_path = (
    "/home/hlxu/download/fastspeech2_nosil_baker_ckpt_0.4/speech_stats.npy"
)
pwg_config_path = "/home/hlxu/download/pwg_baker_ckpt_0.4/pwg_default.yaml"
pwg_checkpoint_path = (
    "/home/hlxu/download/pwg_baker_ckpt_0.4/pwg_snapshot_iter_400000.pdz"
)
pwg_stat_path = "/home/hlxu/download/pwg_baker_ckpt_0.4/pwg_stats.npy"
phones_dict = "/home/hlxu/download/fastspeech2_nosil_baker_ckpt_0.4/phone_id_map.txt"

with open(fastspeech2_config_path) as f:
    fastspeech2_config = CfgNode(yaml.safe_load(f))
with open(pwg_config_path) as f:
    pwg_config = CfgNode(yaml.safe_load(f))
with open(phones_dict, "r") as f:
    phn_id = [line.strip().split() for line in f.readlines()]

vocab_size = len(phn_id)
odim = fastspeech2_config.n_mels


class TTS:
    def __init__(self):
        self.frontend = Frontend(phone_vocab_path=phones_dict)
        print("Frontend done!")

        model = FastSpeech2(idim=vocab_size, odim=odim, **fastspeech2_config["model"])
        # 加载预训练模型参数
        model.set_state_dict(paddle.load(fastspeech2_checkpoint_path)["main_params"])
        model.eval()
        # 读取数据预处理阶段数据集的均值和标准差
        stat = np.load(fastspeech2_stat_path)
        mu, std = stat
        mu, std = paddle.to_tensor(mu), paddle.to_tensor(std)
        # 构造归一化的新模型
        fastspeech2_normalizer = ZScore(mu, std)
        self.fastspeech2_inference = FastSpeech2Inference(fastspeech2_normalizer, model)
        self.fastspeech2_inference.eval()
        print("FastSpeech2 done!")

        # 模型加载预训练参数
        vocoder = PWGGenerator(**pwg_config["generator_params"])
        vocoder.set_state_dict(paddle.load(pwg_checkpoint_path)["generator_params"])
        vocoder.remove_weight_norm()
        vocoder.eval()
        # 读取数据预处理阶段数据集的均值和标准差
        stat = np.load(pwg_stat_path)
        mu, std = stat
        mu, std = paddle.to_tensor(mu), paddle.to_tensor(std)
        pwg_normalizer = ZScore(mu, std)
        # 构建归一化的模型
        self.pwg_inference = PWGInference(pwg_normalizer, vocoder)
        self.pwg_inference.eval()
        print("Parallel WaveGAN done!")
        self.inference("你好")

    def inference(self, text):
        phone_ids = self.frontend.get_input_ids(
            text, merge_sentences=True, print_info=True
        )["phone_ids"][0]
        with paddle.no_grad():
            mel = self.fastspeech2_inference(phone_ids)
            wav = self.pwg_inference(mel)
        wav_bytes = io.BytesIO()
        write(wav_bytes, fastspeech2_config.fs, wav.numpy())
        return bytes2bs64(wav_bytes.read())


class MixTTS(TTSExecutor):
    def postprocess(self, output: str = "output.wav") -> Union[str, os.PathLike]:
        """
        Output postprocess and return results.
        This method get model output from self._outputs and convert it into human-readable results.

        Returns:
            Union[str, os.PathLike]: Human-readable results such as texts and audio files.
        """
        wav_bytes = io.BytesIO()
        write(wav_bytes, self.am_config.fs, self._outputs["wav"].numpy())
        return bytes2bs64(wav_bytes.read())

    def __init__(
        self,
        device: str = "gpu:2",
        am: str = "fastspeech2_mix",
        voc: str = "hifigan_aishell3",
        spk_id: int = 71,
        lang: str = "mix",
    ):
        super(MixTTS, self).__init__()
        self.am = am
        self.voc = voc
        self.spk_id = spk_id
        self.lang = lang
        self.device = device
        self(
            text="你好，我是Samantha, 有什么可以帮到你的吗？",
            lang=lang,
            device=device,
            am=am,
            voc=voc,
            spk_id=spk_id,  # 26, 62, 68, 71, 91, 103, 108, 120, 125, 126, 127, 137
        )

    def inference(self, text):
        return self(
            text=text,
            lang=self.lang,
            device=self.device,
            am=self.am,
            voc=self.voc,
            spk_id=self.spk_id,
        )


if __name__ == "__main__":
    import gradio as gr

    # TTSModel = TTS()
    MixTTSModel = MixTTS()

    gr.Interface(fn=MixTTSModel.inference, inputs="text", outputs="text").launch(
        server_name="0.0.0.0", server_port=7892
    )
