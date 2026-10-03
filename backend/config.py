import os
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import json

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
DATASET_DIR = BASE_DIR / "dataset"
MODELS_DIR = BASE_DIR / "models"
VIDEOS_INPUT_DIR = BASE_DIR / "videos" / "input"
VIDEOS_OUTPUT_DIR = BASE_DIR / "videos" / "output"
REPORTS_DIR = BASE_DIR / "reports"
DB_PATH = BACKEND_DIR / "database" / "traffic.db"
CONFIG_FILE = BACKEND_DIR / "system_config.json"

# Ensure all primary folders exist
for folder in [MODELS_DIR, VIDEOS_INPUT_DIR, VIDEOS_OUTPUT_DIR, REPORTS_DIR, BACKEND_DIR / "database"]:
    folder.mkdir(parents=True, exist_ok=True)


class LaneROI(BaseModel):
    # Normalized coordinates [x1, y1, x2, y2] from 0.0 to 1.0
    # or absolute pixel coordinates; also accepts [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] quads
    box: List = Field(..., description="[x1, y1, x2, y2] or 4-corner quad")


class TrafficSystemConfig(BaseModel):
    # Detection Settings
    confidence_threshold: float = 0.40
    iou_threshold: float = 0.45
    model_path: str = str(MODELS_DIR / "yolov8n.pt")
    custom_model_path: str = str(MODELS_DIR / "best.pt")
    target_classes: List[int] = [2, 3, 5, 7]  # COCO: 2:car, 3:motorcycle, 5:bus, 7:truck
    # UA-DETRAC class mapping: 0: car, 1: van, 2: bus, 3: others

    # Signal & Adaptive Timing Settings
    min_green_time: int = 5
    max_green_time: int = 40
    yellow_time: int = 3
    all_red_time: int = 1
    headway_seconds: float = 2.2  # seconds needed per queued vehicle to cross
    start_window_seconds: float = 2.5  # initial green window for the first vehicle

    # Priority Algorithm Weights
    density_weight: float = 0.6
    waiting_weight: float = 0.4
    starvation_threshold_seconds: float = 45.0  # Maximum waiting time before guaranteed green boost

    # Speed threshold for considering a tracked vehicle as "waiting" (pixels per second or movement delta)
    waiting_speed_threshold: float = 3.5

    # Density thresholds (counts)
    density_low_max: int = 5
    density_medium_max: int = 10
    # > 10 is HIGH

    # Default ROIs (normalized 0.0 to 1.0 for 4-way intersection)
    # Each value is either [x1, y1, x2, y2] (axis-aligned box) or a quad:
    #   [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] (rotated / free-form lane marking)
    # NORTH: top approach
    # SOUTH: bottom approach
    # WEST: left approach
    # EAST: right approach
    rois: Dict[str, list] = {
        "NORTH": [0.35, 0.00, 0.65, 0.40],
        "SOUTH": [0.35, 0.60, 0.65, 1.00],
        "WEST":  [0.00, 0.35, 0.40, 0.65],
        "EAST":  [0.60, 0.35, 1.00, 0.65],
    }

    # Center intersection bounding box (vehicles inside intersection are crossing, not waiting)
    intersection_box: List[float] = [0.40, 0.40, 0.60, 0.60]

    # Processing options
    processing_fps: int = 15  # configurable target FPS for processing
    active_source: str = "simulation"  # 'simulation' or 'video'
    selected_video: Optional[str] = None
    adaptive_mode: bool = True  # True: AI adaptive, False: manual signal control


def load_config() -> TrafficSystemConfig:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return TrafficSystemConfig(**data)
        except Exception as e:
            print(f"[Config] Error loading {CONFIG_FILE}, using defaults: {e}")
    config = TrafficSystemConfig()
    save_config(config)
    return config


def save_config(config: TrafficSystemConfig) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(config.model_dump_json(indent=2))
    except Exception as e:
        print(f"[Config] Error saving {CONFIG_FILE}: {e}")
