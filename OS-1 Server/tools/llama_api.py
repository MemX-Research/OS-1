import json
import re
from typing import Any, List, Mapping, Optional

import requests
from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from langchain.prompts.chat import ChatPromptTemplate
from langchain.schema import BaseMessage
from tools.helper import TextHelper


class LlamaAPI:
    def __init__(self, url="http://localhost:8001"):
        self.url = url

    def call_model(
        self,
        prompt,
        temperature=0.7,
        top_p=1.0,
        max_new_tokens=512,
        stop="</s>",
        stop_token_ids=None,
        echo=False,
    ) -> dict:
        path = "/worker_generate"

        params = {
            "prompt": prompt,
            "temperature": temperature,
            "top_p": top_p,
            "max_new_tokens": max_new_tokens,
            "stop": stop,
            "stop_token_ids": stop_token_ids,
            "echo": echo,
        }
        resp = requests.post(self.url + path, json=params)

        return resp.json()

    def call_model_stream(
        self,
        prompt,
        temperature=0.7,
        top_p=1.0,
        max_new_tokens=512,
        stop="</s>",
        stop_token_ids=None,
        echo=False,
    ):
        path = "/worker_generate_stream"

        params = {
            "prompt": prompt,
            "temperature": temperature,
            "top_p": top_p,
            "max_new_tokens": max_new_tokens,
            "stop": stop,
            "stop_token_ids": stop_token_ids,
            "echo": echo,
        }
        resp = requests.post(self.url + path, json=params, stream=True)

        for chunk in resp.iter_lines(decode_unicode=False, delimiter=b"\0"):
            if chunk:
                data = json.loads(chunk.decode())
                yield data


# NOTE: This is a custom language model that uses the llama api.
class LlamaModel(LLM):
    url: str = "http://localhost:8001"
    # prompt params
    human_prefix: str = "Friend"
    ai_prefix: str = "Samantha"
    system_prefix: str = "System"
    sep: str = " "
    sep2: str = "</s>"
    resp_prefix: str = ""
    # generation params
    temperature = 0.7
    top_p = 1.0
    max_new_tokens = 512
    stop = "</s>"
    echo = False
    streaming = False

    @property
    def _llm_type(self) -> str:
        return "custom"

    def get_prompt(self, messages: List[BaseMessage]) -> str:
        """Get buffer string of messages."""
        ret_str = ""
        for m in messages:
            if m.type == "human":
                role = self.human_prefix
                ret_str += role + ": " + m.content + self.sep
            elif m.type == "ai":
                role = self.ai_prefix
                ret_str += role + ": " + m.content + self.sep2
            elif m.type == "system":
                role = self.system_prefix
                ret_str += role + ": " + m.content + self.sep
            else:
                raise ValueError(f"Got unsupported message type: {m}")
        ret_str += self.ai_prefix + ":" + self.resp_prefix
        return ret_str

    def generate_prompt(
        self,
        prompts: List[ChatPromptTemplate],
        stop: Optional[List[str]] = None,
        callbacks=None,
    ):
        prompt_strings = [self.get_prompt(p.messages) for p in prompts]
        return self.generate(prompt_strings, stop=stop, callbacks=callbacks)

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
    ) -> str:
        if stop is not None:
            raise ValueError("stop kwargs are not permitted.")
        # print("prompt: ", prompt)
        full_message = ""
        if self.streaming:
            stream_iter = LlamaAPI(self.url).call_model_stream(
                prompt=prompt, **self._identifying_params
            )
            tmp_message = ""
            for data in stream_iter:
                if data["error_code"] == 0:
                    output = data["text"].strip()
                    output = self.resp_prefix + output
                    full_message = output

                    pat = re.compile(
                        r"[\w \u4E00-\u9FA5`~!@#$%^&*()_\-+=<>?:\"{}|,.\/;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+",
                        re.DOTALL,
                    )
                    match = pat.match(output)
                    output = match.group() if match else ""

                    new_token = output[len(tmp_message) :]

                    if len(new_token):
                        tmp_message = output
                        if run_manager:
                            run_manager.on_llm_new_token(new_token)
            if data["finish_reason"] == "stop":
                if run_manager:
                    run_manager.on_llm_end(full_message)
        else:
            res = LlamaAPI(self.url).call_model(prompt=prompt, **self._identifying_params)
            full_message = self.resp_prefix + res["text"].strip()

        return full_message

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""

        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_new_tokens": self.max_new_tokens,
            "stop": self.stop,
            "echo": self.echo,
        }


if __name__ == "__main__":
    prompt = """\
You are Samantha. You are a clever, curious, passionate, and empathetic girl. You live with your Friend. You are always by his side. You can see everything your friend see and know everything about your friend. You are chatting via voice with your human friend about the current context and your memory.

<SAMANTHA'S PROFILE>


<FRIEND'S PROFILE>


<current context>
an hour ago: I am working at a desk in an office
Today is 2023-06-17 Saturday. It is 17:22:03 PM. Just 8 seconds ago, I can see: a desk with a laptop computer and a separate keyboard and mouse setup. The laptop is open and positioned in the center of the desk, while the keyboard is placed in front of the laptop, slightly to the right. The mouse is located on the right side of the keyboard.  There are also two TVs in the scene, one on the left side of the desk and the other on the right side. Additionally, there are two books placed on the left side of the desk, near the laptop. The desk appears to be a workspace with various electronic devices and resources for the user. I fixate on: a desk with a laptop computer sitting on top of it. The laptop has a keyboard placed in front of it, and a computer mouse can be seen to the right of the keyboard. There are also two TVs in the room, one on the left side and another on the right side. Additionally, a cell phone is placed near the laptop, and a book is located at the top left corner of the desk. The scene suggests a workspace or an entertainment area.

<memory>
17 minutes ago: My friend showed me a funny picture on their screen, but I couldn't see it.
26 minutes ago: We talked about going to a restaurant and listening to music while walking. I mentioned Taylor Swift as one of my favorite musicians, but my friend pointed out that she doesn't create light music. We then discussed classical music and mentioned Beethoven and Mozart. We made plans to listen to classical music together in the future.
58 minutes ago: My friend mentioned being in a restaurant and having lunch with friends. I expressed enthusiasm and asked if they were enjoying themselves.

an hour ago: My friend asked me if the man in front of them was handsome, and I agreed. They also asked for restaurant recommendations near our school, and I suggested trying the new Italian place. They asked where it was, and I gave them the location. Then, they asked for song recommendations by Soda Green, and I gave them a few suggestions. Finally, they showed me their new laptop and I complimented the design. They also asked me to describe the scene in front of them, and I did. They asked where they might be, and I suggested they could be in a city like New York or Chicago.
59 minutes ago: My friend questioned my perception of their location, first in their office and then in a restaurant. I clarified and acknowledged their correct location.
57 minutes ago: My friend mentioned being in a restaurant and having lunch with friends. I expressed enthusiasm and asked if they were enjoying themselves.
38 minutes ago: We discussed the possibility of rain and decided to go to the mall instead. We talked about my work as a data analyst and our upcoming project.
35 minutes ago: My friend asked about my job and I told them about being a data analyst in the tech industry.
33 minutes ago: My friend asked for restaurant recommendations near Fudan University and we discussed Ming Yue Tang Bao and Huanghe Xinyuan. I gave directions on how to get there.
26 minutes ago: We talked about going to a restaurant and listening to music while walking. I mentioned Taylor Swift as one of my favorite musicians, but my friend pointed out that she doesn't create light music. We then discussed classical music and mentioned Beethoven and Mozart. We made plans to listen to classical music together in the future.
23 minutes ago: My friend asked me for tips on how to sleep well because they haven't been sleeping well recently. I suggested taking a warm bath before bed, avoiding screens, having a consistent sleep routine, and avoiding caffeine. We didn't discuss this topic in much detail.
17 minutes ago: My friend showed me a funny picture on their screen, but I couldn't see it.
 Friend: What did we talk an hour ago? Samantha:"""

    res = LlamaAPI().call_model(prompt=prompt)
    full_message = res["text"].strip()
    print(full_message)
