from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import asyncio
import json
from contextlib import asynccontextmanager

from backend.config import BASE_DIR, load_config, save_config
from backend.database.database import init_db, log_event
from backend.routes.traffic import router as traffic_router
from backend.routes.video import router as video_router
from backend.routes.analytics import router as analytics_router
from backend.routes.model import router as model_router
from backend.routes.reports import router as reports_router
from backend.websocket.traffic_socket import manager
from backend.services.traffic_engine import engine

init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("Backend server starting", "INFO", "SYSTEM")
    engine.start()
    yield
    engine.stop()
    log_event("Backend server stopped", "INFO", "SYSTEM")


app = FastAPI(title="AI Adaptive Traffic Management System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def index():
    return {"message": "AI Adaptive Traffic Management System API is running."}

@app.get("/api/health")
def health_check():
    config = load_config()
    return {
        "status": "ok",
        "service": "backend",
        "model_path": config.model_path,
        "custom_model_path": config.custom_model_path,
        "engine": engine.get_status(),
        "timestamp": "online"
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send the latest engine state immediately after connect
        await websocket.send_text(json.dumps({"type": "state", "data": engine.get_latest_state()}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


app.include_router(traffic_router)
app.include_router(video_router)
app.include_router(analytics_router)
app.include_router(model_router)
app.include_router(reports_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)
