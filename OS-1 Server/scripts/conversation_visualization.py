import sys

import pandas as pd

sys.path.append("..")
sys.path.append(".")

import datetime
import io
import time
from tempfile import NamedTemporaryFile

import gradio as gr
from gradio.context import Context
from gradio import Request as GrRequest
import pymongo
from bson.objectid import ObjectId
from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image
from pydantic import BaseModel
from pydub import AudioSegment

from base.conversation import Conversation
from scripts.usage_statistics import get_conversation_statistics
from templates.response import CHAT_SYSTEM_PROMPT
from tools.authorization import User, UserController, User_prompt, PromptController
from tools.bs64 import bs642bytes
from tools.mongo import MongoClientProxy
from tools.redis_client import RedisClientProxy
from tools.time_fmt import get_past_timestamp, str_to_timestamp, timestamp_to_str
from templates.custom_prompt import DEFAULT_SYS_PROMPT


def UserIdTextBox(args, **kwargs):

    def resume_userid(request: GrRequest):
        return request.username

    component = gr.Textbox(args, **kwargs)
    Context.root_block.load(resume_userid, inputs=[], outputs=component)

    return component

userController = UserController()

# ======= FastAPI APP (register & login)========
app = FastAPI()

app.mount("/static", StaticFiles(directory="scripts/static"), name="static")

templates = Jinja2Templates(directory="scripts/static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse("/register")


@app.get("/register", response_class=HTMLResponse)
async def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request, user_id: str = Form(), password: str = Form()
):
    ret = userController.add_user(user_id, password)

    # Check if the user_id already exists
    if not ret:
        # flash("user_id already exists. Please choose another.", "error")
        error_message = "user_id already exists. Please choose another."
        return templates.TemplateResponse(
            "register.html", {"request": request, "error_message": error_message}
        )
    else:
        return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/reset", response_class=HTMLResponse)
async def reset(request: Request):
    return templates.TemplateResponse("reset.html", {"request": request})


@app.post("/reset", response_class=HTMLResponse)
async def reset_post(
    request: Request, user_id: str = Form(), password: str = Form(), token: str = Form()
):
    _token = RedisClientProxy.get_reset_token(user_id)
    if _token is None:
        error_message = f"`{user_id}` was not granted access to reset password."
        return templates.TemplateResponse(
            "reset.html", {"request": request, "error_message": error_message}
        )
    if token != _token:
        error_message = f"Wrong reset token for `{user_id}`. Please check your input."
        return templates.TemplateResponse(
            "reset.html", {"request": request, "error_message": error_message}
        )
    ret = userController.update_password(user_id, password)

    if not ret:
        error_message = f"`{user_id}` does not exist! Please check your input."
        return templates.TemplateResponse(
            "reset.html", {"request": request, "error_message": error_message}
        )
    else:
        RedisClientProxy.del_reset_token(user_id)
        return RedirectResponse("/logout", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/logout")
async def logout():
    # clear cookie
    resp = RedirectResponse("/dashboard")
    resp.delete_cookie("access-token-unsecure")
    resp.delete_cookie("access-token")
    return resp


def authenticate(user_id, password):
    ret = userController.check_password(user_id, password)
    return ret


# ======== Gradio APP ========
def get_users():
    return MongoClientProxy.get_users()


def get_conversations(user_id: str, days: int):
    timestamp = (
        time.mktime(
            time.strptime(
                str(datetime.date.today() - datetime.timedelta(days=int(days))),
                "%Y-%m-%d",
            )
        )
        * 1000
    )
    res = Conversation.find_conversations(
        {"user_id": user_id, "current_time": {"$gte": timestamp}},
        {
            "_id": 0,
            "audio": 0,
        },
        sort=[("current_time", pymongo.ASCENDING)],
        limit=100,
    )
    audio_timestamps = []
    prompt_timestamps = []
    history = []
    prompt = ""
    for item in res:
        history += [(item["human"], item["ai"])]
        prompt = item["prompt"]
        audio_timestamps.append(str(item["current_time"]))
        prompt_timestamps.append(str(item["history_id"]))
    print(history)
    return (
        history,
        prompt,
        gr.Dropdown.update(
            choices=get_image_timestamp(user_id, days), interactive=True
        ),
        gr.Dropdown.update(choices=audio_timestamps, interactive=True),
        gr.Dropdown.update(choices=prompt_timestamps, interactive=True),
    )


def get_image(user_id: str, timestamp: int):
    if timestamp is None:
        return None, None
    try:
        timestamp = int(timestamp)
    except:
        timestamp = str_to_timestamp(timestamp, format="%Y-%m-%d %H:%M:%S.%f")
    res = MongoClientProxy.find_contexts(
        {"user_id": user_id, "current_time": timestamp},
        {
            "_id": 0,
        },
    )
    for item in res:
        image_str = item["visual_image"]
        scene_bytes = bs642bytes(image_str)
        scene_image = Image.open(io.BytesIO(scene_bytes))
        context = []
        if item["current_time"] is not None:
            context.append(
                f'Time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["current_time"] / 1000))}'
            )
        if item["location"] is not None:
            context.append(f'Location: {item["location"]}')
        if item["scene"] is not None:
            context.append(f'Scene: {item["scene"]}')
        if item["attention"] is not None:
            context.append(f'Attention: {item["attention"]}')
        context_str = "\n".join(context)
        return scene_image, context_str
    return None, None


def get_audio(user_id: str, timestamp: str):
    res = Conversation.find_conversations(
        {"user_id": user_id, "current_time": int(timestamp)},
        {
            "_id": 0,
        },
    )
    for item in res:
        audio_str = item["audio"]
        if audio_str is None or audio_str == "":
            continue
        wav_data = AudioSegment.from_wav(io.BytesIO(bs642bytes(audio_str)))
        wav_path = NamedTemporaryFile(suffix="wav").name
        wav_data.export(wav_path, format="wav")
        return wav_path, item["human"]
    return None, None


def get_prompt(user_id: str, prompt_id: str):
    res = MongoClientProxy.find_histories(
        {"user_id": user_id, "_id": ObjectId(prompt_id)},
    )
    print(prompt_id)
    for item in res:
        prompt = CHAT_SYSTEM_PROMPT.format(
            samantha_personality=item["samantha_personality"],
            samantha_experience=item["samantha_experience"],
            samantha_thought=item["samantha_thought"],
            samantha_feeling=item["samantha_feeling"],
            human_personality=item["human_personality"],
            human_experience=item["human_experience"],
            human_thought=item["human_thought"],
            human_feeling=item["human_feeling"],
            conversation_summary=item["conversation_summary"],
            context_summary=item["context_summary"],
            objective=item["objective"],
            instruction=item["instruction"],
            style=item["style"],
            human_memory=item["human_memory"],
            samantha_memory=item["samantha_memory"],
            context=item["context"],
        )
        return prompt
    return None


def get_image_timestamp(user_id: str, days: int):
    timestamp = (
        time.mktime(
            time.strptime(
                str(datetime.date.today() - datetime.timedelta(days=int(days))),
                "%Y-%m-%d",
            )
        )
        * 1000
    )
    res = MongoClientProxy.find_contexts(
        {"user_id": user_id, "current_time": {"$gte": timestamp}},
        {
            "_id": 0,
        },
    ).sort("current_time", pymongo.ASCENDING)
    timestamps = []
    for item in res:
        ts = int(item["current_time"])
        name = timestamp_to_str(ts, format="%Y-%m-%d %H:%M:%S.%f")[:-3]
        # timestamps.append((name, ts)) # gradio==3.45.2 版本支持设置name+value但有bug拖不了进度条，只能回退3.35.2
        timestamps.append(name)
    # print(timestamps)
    return timestamps


# plot
def plot_statistics(user_id, days, plot_type):
    day_stat, hour_stat = get_conversation_statistics(
        user_id, get_past_timestamp(days, day_start_hour=0), get_past_timestamp()
    )
    day_df = pd.DataFrame(day_stat)
    hour_df = pd.DataFrame(hour_stat)

    out_date_df = gr.DataFrame.update(day_df.copy(), interactive=False)

    # date to pd.Timestamp
    # day_df["date"] = pd.to_datetime(day_df["date"])
    day_plot = gr.LinePlot.update(
        day_df,
        x="date",
        y=plot_type,
        color_legend_position="bottom",
        title=plot_type,
        height=300,
        width=500,
        interactive=True,
    )

    hour_plot = gr.LinePlot.update(
        hour_df,
        x="hour",
        y="avg_rounds",
        color_legend_position="bottom",
        title="Average rounds per hour",
        height=300,
        width=500,
        interactive=True,
    )
    # skip zero
    avg_rounds = day_df[day_df["rounds"] > 0]["rounds"].mean()
    avg_minutes = day_df[day_df["minutes"] > 0]["minutes"].mean()
    usage_text = f"Average rounds per day: {avg_rounds:.2f}\nAverage usage time per day: {avg_minutes:.2f} min"

    return day_plot, out_date_df, hour_plot, usage_text


def save_prompt(user_id, title, content):
    return PromptController().add_prompt(user_id, title, content)


title_prompt_mapping = {} #哈希表映射title和prompt_id

def get_prompt_list(user_id):
    documents = PromptController.collection.find({"user_id": user_id})
    
    title_names = []
    
    for doc in documents:
        title = doc["title"]
        prompt_id = doc["prompt_id"]
        title_names.append(title)
        title_prompt_mapping[title] = prompt_id
        
    return (gr.Dropdown.update(choices=title_names, interactive=True))

def prompt_update(user_id, title):
    user_collection = UserController().collection #user表
    prompt_collection = PromptController().collection #prompt表
    
    current_prompt_id = title_prompt_mapping[title] 

    filter = {"user_id": user_id}
    update = {"$set": {"current_promptid": current_prompt_id}}

    user_collection.update_one(filter, update) #更新user_id对应的目前使用的prompt_id
    result = prompt_collection.find_one({"prompt_id":current_prompt_id})
    if result:
        new_title = result["title"]
        new_content = result["content"]
    else:
        new_title = ""
        new_content = ""
    update = {"$set": {"system_prompt": new_content}}   
    user_collection.update_one(filter, update) #更新userid对应的目前使用的prompt内容
    
    return (gr.Textbox.update(new_title), gr.Textbox.update(new_content))
    
    
def clear_content():
    new_title = ""
    new_content = ""
        
    return (gr.Textbox.update(new_title), gr.Textbox.update(new_content))
    
with gr.Blocks() as demo:
    gr.Markdown(value="## View chat log & captured images")
    with gr.Row():
        with gr.Group():
            user_id = UserIdTextBox(
                f"None",
                label="User ID",
                lines=1,
                interactive=False,
                scale=1,
            )
            # user_btn = gr.Button(value="获取用户信息", variant="primary", size="sm")
            logout_btn = gr.Markdown(value="[Logout](/logout)", rtl=True)
        # user_id = gr.Request()
        days = gr.Slider(1, 365, value=1, step=1, label="最近几天", scale=3)
    with gr.Column():
        chatbot = gr.Chatbot(label="聊天记录")
        history = gr.Textbox(label="最新历史", lines=1)
    with gr.Row():
        image_timestamp = gr.Dropdown(choices=[], label="图片时间戳")
        image = gr.Image(label="图片")
        caption = gr.Textbox(label="Caption")
    with gr.Row():
        audio_timestamp = gr.Dropdown(choices=[], label="音频时间戳", visible=False)
        audio = gr.Audio(label="音频", visible=False)
        text = gr.Textbox(label="文本", visible=False)
    with gr.Row():
        prompt_id = gr.Dropdown(choices=[], label="PromptID", visible=False)
        prompt = gr.Textbox(label="Prompt", visible=False)
    # statistics
    gr.Markdown(value="## Usage Statistics")
    with gr.Row():
        with gr.Column():
            plot_slider = gr.Slider(7, 365, value=7, step=1, label="最近几天")
            plot_type = gr.Radio(["rounds", "minutes", "sessions"], label="统计类型")
            user_statistic_text = gr.Textbox(label="平均使用情况", lines=1)
        with gr.Column():
            date_stat_plot = gr.LinePlot()
            hour_stat_plot = gr.LinePlot()
    with gr.Row():
        date_stat_df = gr.DataFrame()
    #prompt
    gr.Markdown(value="## System prompt edition")  
    with gr.Row():
        with gr.Column():
            prompt_title = gr.Dropdown(choices=[], label="Prompt History")
            gr.Markdown(
            """
            [Tips]:
            1. Select the system prompt you have [Saved] in [Prompt history]. Once you select one of the items, it will be automatically set as the current system prompt on which Samantha is based.
            2. [Prompt title]: The name you give to the system prompt you edited.
            3. [Prompt content]: The content of the system prompt you edited.
            """)
        with gr.Column():
            with gr.Row():
                current_prompt_title = gr.Textbox(label="Prompt title",lines=1)
            with gr.Row():
                prompt_text = gr.Textbox(label="Prompt content",lines=8)
            with gr.Row():
                    save_btn = gr.Button(value="Save", variant="primary", size="sm")
                    clear_btn = gr.Button(value="New", variant="primary", size="sm")
    with gr.Row():
        ref_prompt = gr.Textbox(label="Default system prompt", lines=1, value=DEFAULT_SYS_PROMPT)

    save_btn.click(
        save_prompt,
        [user_id, current_prompt_title, prompt_text],
        [user_id, current_prompt_title, prompt_text],
    ).then(
        get_prompt_list,
        [user_id],
        [prompt_title]
    )
    user_id.change(
        get_prompt_list,
        [user_id],
        [prompt_title]
    ).then(
        get_conversations,
        [user_id, days],
        [chatbot, history, image_timestamp, audio_timestamp, prompt_id],
    )
    prompt_title.change(
        prompt_update,
        [user_id,prompt_title],
        [current_prompt_title,prompt_text]
    )
    clear_btn.click(
        clear_content,
        [],
        [current_prompt_title,prompt_text],
    )
    days.release(
        get_conversations,
        [user_id, days],
        [chatbot, history, image_timestamp, audio_timestamp, prompt_id],
    )
    image_timestamp.change(get_image, [user_id, image_timestamp], [image, caption])
    audio_timestamp.change(get_audio, [user_id, audio_timestamp], [audio, text])
    prompt_id.change(get_prompt, [user_id, prompt_id], [prompt])
    plot_slider.release(
        plot_statistics,
        [user_id, plot_slider, plot_type],
        [date_stat_plot, date_stat_df, hour_stat_plot, user_statistic_text],
    )
    plot_type.change(
        plot_statistics,
        [user_id, plot_slider, plot_type],
        [date_stat_plot, date_stat_df, hour_stat_plot, user_statistic_text],
    )

demo.auth = authenticate
demo.auth_message = "Welcome to EgoChat Dashboard!"
app = gr.mount_gradio_app(app, demo, path="/dashboard")


if __name__ == "__main__":
    import uvicorn

    # debug
    DEBUG = False
    if DEBUG:
        uvicorn.run("conversation_visualization:app", reload=True, port=5000)
    else:
        uvicorn.run("conversation_visualization:app", host="0.0.0.0", port=5156)
