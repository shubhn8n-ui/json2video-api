import uuid
import os
import threading
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from moviepy.editor import *
import requests

app = FastAPI()

JOBS = {}
RESULT_FOLDER = "static"
os.makedirs(RESULT_FOLDER, exist_ok=True)


class Element(BaseModel):
    type: str
    src: str = None
    text: str = None
    animation: str = None
    position: str = None
    color: str = None
    background: str = None
    font_size: int = 60


class Scene(BaseModel):
    duration: int
    transition: str = None
    elements: list[Element]


class RenderRequest(BaseModel):
    resolution: str
    scenes: list[Scene]
    elements: list[Element] = []


def download_file(url, filename):
    r = requests.get(url)
    with open(filename, "wb") as f:
        f.write(r.content)


def render_video(job_id, data: RenderRequest):
    try:
        width, height = map(int, data.resolution.split("x"))
        clips = []

        for idx, scene in enumerate(data.scenes):
            for item in scene.elements:
                if item.type == "image":
                    img_path = f"{RESULT_FOLDER}/{job_id}_img{idx}.jpg"
                    download_file(item.src, img_path)
                    clip = ImageClip(img_path).set_duration(scene.duration)
                    clip = clip.resize(1.2)  
                    clips.append(clip)

        final = concatenate_videoclips(clips, method="compose")

        # audio
        audio_file = None
        for e in data.elements:
            if e.type == "audio":
                audio_file = f"{RESULT_FOLDER}/{job_id}_audio.mp3"
                download_file(e.src, audio_file)

        if audio_file:
            final = final.set_audio(AudioFileClip(audio_file))

        output_path = f"{RESULT_FOLDER}/{job_id}.mp4"
        final.write_videofile(output_path, fps=24, codec="libx264")

        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["video_url"] = f"/result/{job_id}.mp4"

    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)


@app.post("/render")
async def render(data: RenderRequest):
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "processing"}

    threading.Thread(target=render_video, args=(job_id, data)).start()

    return {
        "job_id": job_id,
        "status": "processing",
        "video_url": f"/result/{job_id}.mp4"
    }


@app.get("/status/{job_id}")
async def status(job_id: str):
    if job_id not in JOBS:
        return JSONResponse({"error": "Invalid Job ID"}, status_code=404)

    return JOBS[job_id]


@app.get("/result/{filename}")
async def result(filename: str):
    path = f"{RESULT_FOLDER}/{filename}"
    if not os.path.exists(path):
        return JSONResponse({"error": "Not ready"}, status_code=404)

    return FileResponse(path)
