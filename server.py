"""
TaikoNation Web UI Server (FastAPI + Uvicorn)
Provides REST APIs for uploading songs, generating beatmaps (.osu / .osz),
and serving the modern frontend.
"""

import os
import uuid
import glob
import shutil
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import numpy as np

import engine

app = FastAPI(title="TaikoNation Web UI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp_tasks"
TEMP_DIR.mkdir(exist_ok=True)
WEB_DIR = BASE_DIR / "web"
WEB_DIR.mkdir(exist_ok=True)

# Cache model
TAIKO_MODEL = None

def get_model():
    global TAIKO_MODEL
    if TAIKO_MODEL is None:
        TAIKO_MODEL = engine.load_taiko_model()
    return TAIKO_MODEL

tasks_status = {}

@app.on_event("startup")
async def startup_event():
    get_model()

@app.get("/api/presets")
async def get_presets():
    """List available pre-processed songs in input_songs directory"""
    songs = glob.glob(str(BASE_DIR / "input_songs" / "*.npy"))
    preset_list = []
    for s in songs:
        filename = Path(s).name
        # clean filename
        clean_name = filename.replace(" Input.npy", "")
        preset_list.append({
            "id": filename,
            "name": clean_name,
            "path": s
        })
    return {"presets": preset_list}

@app.post("/api/generate")
async def generate_chart(
    file: UploadFile = File(...),
    title: str = Form(""),
    artist: str = Form(""),
    difficulty: str = Form("TaikoNation Oni"),
    temperature: float = Form(0.8),
    density: float = Form(1.0)
):
    """Upload audio and generate osu!taiko beatmap"""
    task_id = str(uuid.uuid4())
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    original_filename = file.filename or "audio.mp3"
    stem = Path(original_filename).stem
    ext = Path(original_filename).suffix.lower() or ".mp3"
    
    song_title = title.strip() or stem
    song_artist = artist.strip() or "Unknown Artist"

    saved_audio_path = task_dir / f"input{ext}"
    with open(saved_audio_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Convert to mp3 if needed using ffmpeg, or copy as audio.mp3
    final_audio_path = task_dir / "audio.mp3"
    if ext == ".mp3":
        shutil.copy(saved_audio_path, final_audio_path)
    else:
        # ffmpeg convert
        cmd = f'ffmpeg -y -i "{saved_audio_path}" -vn -ar 44100 -ac 2 -b:a 192k "{final_audio_path}"'
        proc = await asyncio.create_subprocess_shell(cmd)
        await proc.communicate()
        if not final_audio_path.exists():
            shutil.copy(saved_audio_path, final_audio_path)

    tasks_status[task_id] = {
        "status": "processing",
        "progress": 20,
        "message": "特徴量抽出中 (Analyzing audio features)..."
    }

    try:
        # Extract features
        log_mel, sr, duration = engine.extract_features_from_audio(str(final_audio_path))
        tasks_status[task_id]["progress"] = 60
        tasks_status[task_id]["message"] = "TaikoNation AI 推論中 (Predicting notes)..."

        # Predict
        model = get_model()
        notes = engine.generate_taiko_chart(
            model=model,
            song_features=log_mel,
            title=song_title,
            artist=song_artist,
            difficulty_name=difficulty,
            temperature=temperature,
            density_mult=density
        )

        tasks_status[task_id]["progress"] = 85
        tasks_status[task_id]["message"] = "譜面パッケージング中 (Building .osu & .osz)..."

        osu_content, hit_objects = engine.create_osu_content(
            note_selections=notes,
            title=song_title,
            artist=song_artist,
            difficulty_name=difficulty
        )

        package_filename = f"{song_artist} - {song_title} [{difficulty}].osz"
        # Sanitize filename
        clean_package_filename = "".join(c for c in package_filename if c not in '<>:"/\\|?*')
        osu_path, osz_path = engine.package_osz(
            output_dir=str(task_dir),
            audio_file_path=str(final_audio_path),
            osu_content=osu_content,
            package_name=clean_package_filename
        )

        # Count notes by type
        # 1: Don, 2: Kat, 3: Big Don, 4: Big Kat
        don_count = sum(1 for n in notes if n == 1)
        kat_count = sum(1 for n in notes if n == 2)
        big_don_count = sum(1 for n in notes if n == 3)
        big_kat_count = sum(1 for n in notes if n == 4)
        total_notes = len(hit_objects)

        result_data = {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "title": song_title,
            "artist": song_artist,
            "difficulty": difficulty,
            "duration": round(duration, 1),
            "total_notes": total_notes,
            "don_count": don_count,
            "kat_count": kat_count,
            "big_don_count": big_don_count,
            "big_kat_count": big_kat_count,
            "osz_name": clean_package_filename,
            "notes_preview": notes[:800], # for web lane preview
            "audio_url": f"/api/audio/{task_id}"
        }
        tasks_status[task_id] = result_data
        return result_data

    except Exception as e:
        tasks_status[task_id] = {
            "status": "error",
            "message": str(e)
        }
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-preset")
async def generate_from_preset(
    preset_name: str = Form(...),
    difficulty: str = Form("TaikoNation Oni"),
    temperature: float = Form(0.8),
    density: float = Form(1.0)
):
    """Generate beatmap directly from an existing preprocessed song feature file"""
    preset_path = BASE_DIR / "input_songs" / preset_name
    if not preset_path.exists():
        raise HTTPException(status_code=404, detail="Preset file not found")

    task_id = str(uuid.uuid4())
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    song_features = np.load(preset_path)
    # clean name
    clean_name = preset_name.replace(" Input.npy", "")
    parts = clean_name.split(" - ")
    if len(parts) >= 2:
        artist = parts[0]
        title = " - ".join(parts[1:])
    else:
        artist = "TaikoNation"
        title = clean_name

    model = get_model()
    notes = engine.generate_taiko_chart(
        model=model,
        song_features=song_features,
        title=title,
        artist=artist,
        difficulty_name=difficulty,
        temperature=temperature,
        density_mult=density
    )

    osu_content, hit_objects = engine.create_osu_content(
        note_selections=notes,
        title=title,
        artist=artist,
        difficulty_name=difficulty
    )

    osu_file_path = task_dir / "chart.osu"
    with open(osu_file_path, "w", encoding="utf-8") as f:
        f.write(osu_content)

    duration = round(len(song_features) * 0.023, 1)
    don_count = sum(1 for n in notes if n == 1)
    kat_count = sum(1 for n in notes if n == 2)
    big_don_count = sum(1 for n in notes if n == 3)
    big_kat_count = sum(1 for n in notes if n == 4)
    total_notes = len(hit_objects)

    result_data = {
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "title": title,
        "artist": artist,
        "difficulty": difficulty,
        "duration": duration,
        "total_notes": total_notes,
        "don_count": don_count,
        "kat_count": kat_count,
        "big_don_count": big_don_count,
        "big_kat_count": big_kat_count,
        "has_audio": False,
        "notes_preview": notes[:800]
    }
    tasks_status[task_id] = result_data
    return result_data

@app.get("/api/download/{task_id}/osu")
async def download_osu(task_id: str):
    osu_path = TEMP_DIR / task_id / "chart.osu"
    if not osu_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    info = tasks_status.get(task_id, {})
    title = info.get("title", "chart")
    diff = info.get("difficulty", "TaikoNation")
    return FileResponse(
        osu_path,
        media_type="application/octet-stream",
        filename=f"{title} [{diff}].osu"
    )

@app.get("/api/download/{task_id}/osz")
async def download_osz(task_id: str):
    task_dir = TEMP_DIR / task_id
    osz_files = list(task_dir.glob("*.osz"))
    if not osz_files:
        raise HTTPException(status_code=404, detail="OSZ package not found")
    return FileResponse(
        osz_files[0],
        media_type="application/octet-stream",
        filename=osz_files[0].name
    )

@app.get("/api/audio/{task_id}")
async def get_audio(task_id: str):
    audio_path = TEMP_DIR / task_id / "audio.mp3"
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(audio_path, media_type="audio/mpeg")

# Serve frontend static assets
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

if __name__ == "__main__":
    print("Starting TaikoNation Web UI Server at http://127.0.0.1:8000")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
