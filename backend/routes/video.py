import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import VIDEOS_INPUT_DIR, load_config, save_config
from backend.database.database import log_event
from backend.services.traffic_engine import engine

router = APIRouter(prefix="/api/video", tags=["Video"])

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


class VideoControlRequest(BaseModel):
    action: str  # 'start', 'pause', 'stop', 'restart'
    video_name: Optional[str] = None


@router.get("/list")
def list_videos():
    VIDEOS_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    videos = []
    for f in VIDEOS_INPUT_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
            videos.append({
                "name": f.name,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "path": str(f)
            })
    return {"videos": videos}


@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    VIDEOS_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    target_path = VIDEOS_INPUT_DIR / file.filename

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        log_event(f"Error saving uploaded video: {str(e)}", "ERROR", "UPLOAD")
        raise HTTPException(status_code=500, detail=f"Failed to save video: {str(e)}")

    log_event(f"Video uploaded: {file.filename}", "INFO", "UPLOAD")

    # Update config selected video
    config = load_config()
    config.selected_video = str(target_path)
    save_config(config)

    return {
        "status": "success",
        "filename": file.filename,
        "path": str(target_path),
        "size_mb": round(target_path.stat().st_size / (1024 * 1024), 2)
    }


@router.post("/control")
def control_video(req: VideoControlRequest):
    """Start/pause/stop video-mode processing. Requires a video to be available."""
    action = req.action.lower()

    if action in ("start", "restart"):
        target = req.video_name
        if not target:
            # use the last selected video from config, or the first found file
            config = load_config()
            if config.selected_video and os.path.exists(config.selected_video):
                target = Path(config.selected_video).name
            else:
                VIDEOS_INPUT_DIR.mkdir(parents=True, exist_ok=True)
                found = [f for f in VIDEOS_INPUT_DIR.iterdir() if f.suffix.lower() in ALLOWED_EXTENSIONS]
                if found:
                    target = found[0].name
        if not target:
            raise HTTPException(status_code=404, detail="No video available. Upload a video first.")
        result = engine.start_video_processing(target)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("detail"))
        return {"status": "success", "action": "start", **result}

    if action == "pause":
        paused = engine.toggle_pause()
        return {"status": "success", "action": "pause", "paused": paused}

    if action == "stop":
        engine.stop()
        return {"status": "success", "action": "stop", "running": False}

    raise HTTPException(status_code=400, detail="Action must be start/pause/stop/restart")