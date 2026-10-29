import asyncio
import os
from typing import Dict, Any, Optional

import cv2

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from backend.config import load_config, save_config, TrafficSystemConfig
from backend.database.database import get_recent_logs, log_event, get_recent_emergency_events
from backend.services.traffic_engine import engine

router = APIRouter(prefix="/api/traffic", tags=["Traffic"])


class ModeSwitchRequest(BaseModel):
    mode: str  # 'simulation' or 'video'
    video_name: Optional[str] = None


class EmergencyPreemptionRequest(BaseModel):
    direction: str = "NORTH"             # 'NORTH', 'SOUTH', 'EAST', 'WEST'
    emergency_type: str = "ambulance"    # 'ambulance', 'fire_truck', 'police'
    duration: float = 15.0               # seconds of green light assigned
    vehicle_id: Optional[int] = None
    confidence: Optional[float] = 0.95


class ControlRequest(BaseModel):
    action: str  # 'start', 'pause', 'stop', 'restart'


class ManualSignalRequest(BaseModel):
    direction: str  # 'NORTH', 'SOUTH', 'EAST', 'WEST'
    duration: Optional[float] = 15.0


class AdaptiveRequest(BaseModel):
    adaptive: bool


class ConfigUpdateRequest(BaseModel):
    confidence_threshold: Optional[float] = None
    iou_threshold: Optional[float] = None
    min_green_time: Optional[int] = None
    max_green_time: Optional[int] = None
    yellow_time: Optional[int] = None
    all_red_time: Optional[int] = None
    density_weight: Optional[float] = None
    waiting_weight: Optional[float] = None
    starvation_threshold_seconds: Optional[float] = None
    waiting_speed_threshold: Optional[float] = None
    density_low_max: Optional[int] = None
    density_medium_max: Optional[int] = None
    processing_fps: Optional[int] = None
    adaptive_mode: Optional[bool] = None
    rois: Optional[Dict[str, list]] = None
    intersection_box: Optional[list] = None
    target_classes: Optional[list] = None


@router.get("/config")
def get_system_config():
    config = load_config()
    return config.model_dump()


@router.post("/config")
def update_system_config(req: ConfigUpdateRequest):
    config = load_config()
    update_data = req.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if hasattr(config, k) and v is not None:
            setattr(config, k, v)
    save_config(config)
    engine.reload_config()
    log_event("Traffic system configuration updated", "INFO", "CONFIG")
    return {"status": "success", "config": config.model_dump()}


@router.get("/logs")
def get_logs(limit: int = 50):
    return get_recent_logs(limit)


@router.get("/state")
def get_live_state():
    return engine.get_latest_state()


@router.get("/frame_still")
def get_frame_still():
    """
    A clean (no overlays) still frame from the selected video, used for
    calibrating the lane markings.
    """
    path = engine.config.selected_video
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No video selected")
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Cannot open video file")
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise HTTPException(status_code=500, detail="Could not read frame")
    ret, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ret:
        raise HTTPException(status_code=500, detail="Could not encode frame")
    return Response(content=jpg.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/status")
def get_engine_status():
    return engine.get_status()


@router.get("/stream")
async def stream_live_feed():
    """
    MJPEG stream of the annotated simulation / video frame.
    Consume as an <img src="/api/traffic/stream"> in the browser.
    """
    async def generate():
        last_seq = -1
        while True:
            seq, jpeg = engine.get_latest_frame_jpeg()
            if seq != last_seq and jpeg is not None:
                last_seq = seq
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
            await asyncio.sleep(0.04)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*"},
    )


@router.post("/mode")
async def switch_mode(req: ModeSwitchRequest):
    if req.mode not in ["simulation", "video"]:
        raise HTTPException(status_code=400, detail="Mode must be 'simulation' or 'video'")
    engine.switch_mode(req.mode, req.video_name)
    return {"status": "success", "mode": engine.mode, "running": engine.is_running}


@router.post("/control")
async def control_engine(req: ControlRequest):
    action = req.action.lower()
    if action == "start":
        engine.start()
        return {"status": "success", "action": "start", "running": engine.is_running}
    if action == "pause":
        paused = engine.toggle_pause()
        return {"status": "success", "action": "pause", "paused": paused}
    if action == "stop":
        engine.stop()
        return {"status": "success", "action": "stop", "running": False}
    if action == "restart":
        engine.restart()
        return {"status": "success", "action": "restart", "running": engine.is_running}
    raise HTTPException(status_code=400, detail="Action must be start/pause/stop/restart")


@router.post("/signal/manual")
def manual_signal(req: ManualSignalRequest):
    result = engine.manual_signal(req.direction, req.duration or 15.0)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("detail"))
    return result


@router.post("/signal/adaptive")
def set_adaptive(req: AdaptiveRequest):
    return engine.set_adaptive(req.adaptive)


@router.post("/emergency-preemption")
def emergency_preemption(req: EmergencyPreemptionRequest):
    """
    TEST/SIMULATION & CONTROL ENDPOINT:
    Simulates an approaching emergency vehicle to demonstrate safe signal preemption.
    Transitions safely: Current GREEN -> YELLOW (clearance) -> ALL_RED -> Emergency GREEN.
    """
    result = engine.trigger_emergency_preemption(
        direction=req.direction,
        duration=req.duration or 15.0,
        emergency_type=req.emergency_type or "ambulance",
        vehicle_id=req.vehicle_id,
        confidence=req.confidence or 0.95
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("detail"))
    return result


@router.post("/emergency-clear")
def clear_emergency():
    """Clears active emergency preemption mode and safely resumes normal adaptive control."""
    result = engine.clear_emergency_preemption()
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("detail"))
    return result


@router.get("/emergency-events")
def list_emergency_events(limit: int = 20):
    """Retrieves recent emergency events logged in SQLite."""
    return get_recent_emergency_events(limit)