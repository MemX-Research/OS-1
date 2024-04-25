import asyncio
import json
import threading
import time
from typing import List, Optional
import os
from fastapi import FastAPI, Body, File, UploadFile
from pydantic import BaseModel
from starlette.responses import Response, StreamingResponse

from tools.bs64 import bytes2bs64, bs642bytes_with_padding
from tools.log import logger
from tools.redis_client import RedisClientProxy, UserStatus
from tools.time_fmt import get_timestamp
from tools.nls.token import getTokenFullResponse

app = FastAPI()

accessKeyId = os.getenv("ALI_ACCESS_KEY_ID")
accessKeySecret = os.getenv("ALI_ACCESS_KEY_SECRET")
appKey = os.getenv("ALI_APP_KEY")
hello_msg = """data:audio/wav;base64,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"""


def select_gaze(gazes: List[dict]) -> List[dict]:
    """
    {
        "timestamp": 1680782400000,
        "confidence": 0.8,
        "norm_pos_x": 0.500,
        "norm_pos_y": 0.500,
        "diameter": 10
    }
    """
    gaze_list = []
    for gaze in gazes:
        if 0 < gaze["norm_pos_x"] < 1 and 0 < gaze["norm_pos_y"] < 1:
            gaze_list.append(gaze)
    return gaze_list


def push_image_data(
    timestamp,
    uid,
    scene_bytes,
    gazes,
):
    data = {
        "current_time": get_timestamp(),
        "user_id": uid,
        "scene_bytes": bytes2bs64(scene_bytes),
        "gazes": gazes,
    }
    RedisClientProxy.push_image_data(json.dumps(data))
    logger.error("push image data: {:.2f}s".format(time.time() - timestamp / 1000))


def push_audio_data(timestamp, uid, voice_bytes):
    data = {
        "current_time": get_timestamp(),
        "user_id": uid,
        "voice_bytes": bytes2bs64(voice_bytes),
    }
    RedisClientProxy.push_audio_data(uid, json.dumps(data))
    logger.error("push audio data: {:.2f}s".format(time.time() - timestamp / 1000))


class HeartbeatIn(BaseModel):
    timestamp: int
    uid: str
    gazes: List[dict]

    @classmethod
    def __get_validators__(cls):
        yield cls.validate_to_json

    @classmethod
    def validate_to_json(cls, value):
        if isinstance(value, str):
            return cls(**json.loads(value))
        return value


class HeartbeatOut(BaseModel):
    """
    {
        "status": 1,
        "response": {
            "message": {
                "text": "Have you gone yet?",
                "voice": "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="
            }
        }
    }
    """

    status: int = 0  # 0: 无内容 1: 有消息返回
    response: dict = None


@app.post("/heartbeat")
async def heartbeat(
    data: HeartbeatIn = Body(...),
    voice_file: Optional[UploadFile] = File(None),
    scene_file: Optional[UploadFile] = File(None),
):
    timestamp = data.timestamp
    uid = data.uid
    gazes = select_gaze(data.gazes)
    voice_bytes = None
    scene_bytes = None

    if uid is None or uid == "":
        return

    if voice_file is not None:
        voice_bytes = await voice_file.read()
    if scene_file is not None:
        scene_bytes = await scene_file.read()

    RedisClientProxy.add_user(uid)

    if scene_bytes is not None and len(gazes) > 0:
        threading.Thread(
            target=push_image_data,
            args=(timestamp, uid, scene_bytes, gazes),
        ).start()

    if voice_bytes is not None:
        threading.Thread(
            target=push_audio_data,
            args=(timestamp, uid, voice_bytes),
        ).start()


@app.get("/interrupt/{uid}")
async def interrupt(uid: str):
    if RedisClientProxy.get_user_status(uid) == UserStatus.UNDER_PROCESSING:
        print("set interrupt")
        RedisClientProxy.set_user_status(uid, UserStatus.INTERRUPT)
    return {"status": 1}

@app.get("/get_token")
async def get_token():
    try:
        token = getTokenFullResponse(accessKeyId, accessKeySecret)
        return {"status": 1, 
                "token": token["Id"],
                "expire_time": token["ExpireTime"]}
    except Exception as e:
        logger.error("ali asr token error:{}".format(e))
        return {"status": 0}

@app.get("/response/{uid}", response_model=HeartbeatOut)
async def response(uid: str, is_first: bool = False):
    if is_first:
        return {
            "status": 1,
            "response": {
                "message": {
                    "text": "",
                    "voice": hello_msg,
                }
            },
        }

    res = RedisClientProxy.pop_msg(uid)

    if not res:
        return {"status": 0, "response": {}}
    else:
        return {"status": 1, "response": json.loads(res)}


async def get_audio(uid):
    while True:
        await asyncio.sleep(0.01)
        res = RedisClientProxy.pop_msg(uid)
        if res:
            res = json.dumps({"status": 1, "response": json.loads(res)}) + "\r"
            print("stream response: ", res)
            yield res.encode()


@app.get("/response/stream/{uid}", response_model=HeartbeatOut)
async def response(uid: str):
    return StreamingResponse(content=get_audio(uid), media_type="application/json")


@app.get("/response/v2/{uid}", response_model=HeartbeatOut)
async def response(uid: str):
    res = RedisClientProxy.pop_msg(uid)

    if not res:
        return Response(headers={"status": "0", "response": ""})

    res = json.loads(res)
    text = res["message"]["text"].encode("utf-8").decode("latin-1")
    voice = res["message"]["voice"].encode("utf-8").decode("latin-1")

    def get_audio(voice):
        yield voice

    return StreamingResponse(
        content=get_audio(voice),
        headers={"status": "1", "response": text},
    )


@app.get("/response/v3/{uid}", response_model=HeartbeatOut)
async def response(uid: str):
    res = RedisClientProxy.pop_msg(uid)

    if not res:
        return Response(headers={"status": "0", "response": ""})

    res = json.loads(res)
    text = res["message"]["text"].encode("utf-8").decode("latin-1")
    voice = (
        res["message"]["voice"]
        .encode("utf-8")
        .decode("latin-1")
        .replace("data:audio/wav;base64,", "")
    )
    voice = bs642bytes_with_padding(voice)

    def get_audio(voice):
        yield voice

    return StreamingResponse(
        content=get_audio(voice),
        headers={"status": "1", "response": text},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app="data_server:app", host="0.0.0.0", port=9527, workers=16, reload=False
    )
