from langchain.chains import LLMChain
from langchain.chat_models.base import BaseChatModel
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
)


class ChatModel:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def predict_with_msgs(self, chat_prompt: ChatPromptTemplate):
        chatbot = LLMChain(
            llm=self.llm,
            verbose=True,
            prompt=chat_prompt,
        )
        return chatbot.generate([{}]).generations[0]

    def predict_with_prompt(self, prompt: str):
        return self.predict_with_msgs(
            chat_prompt=ChatPromptTemplate.from_messages(
                [SystemMessagePromptTemplate.from_template(prompt)]
            )
        )[0].text


if __name__ == "__main__":
    from tools.openai_api import get_openai_gpt4
    from tools.llama_api import LlamaModel
    from tools.openai_api import StreamingCallbackHandler
    from multiprocessing import Queue
    from langchain.callbacks.manager import CallbackManager

    import time

    start = time.time()

    queue = Queue()
    # chatbot = ChatModel(
    #     llm=get_openai_gpt4(
    #         streaming=True,
    #         callback_manager=CallbackManager([StreamingCallbackHandler(queue)]),
    #     )
    # )
    chatbot = ChatModel(
        llm=LlamaModel(
            max_new_tokens=512,
            streaming=True,
            callback_manager=CallbackManager([StreamingCallbackHandler(queue)]),
        )
    )

    chat_msgs = [
        SystemMessagePromptTemplate.from_template("You are a helpful assistant."),
        HumanMessagePromptTemplate.from_template("你好啊"),
        AIMessagePromptTemplate.from_template("我是Samantha, 很高兴认识你"),
        HumanMessagePromptTemplate.from_template("给我讲个笑话吧"),
    ]
    chat_prompt = ChatPromptTemplate.from_messages(chat_msgs)
    res = chatbot.predict_with_msgs(chat_prompt=chat_prompt)
    print(res)

    print(time.time() - start)
