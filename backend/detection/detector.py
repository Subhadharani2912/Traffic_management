import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

# Mapping for COCO vehicle classes
COCO_VEHICLE_MAP = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

# Mapping for UA-DETRAC classes
DETRAC_CLASS_MAP = {
    0: "car",
    1: "van",
    2: "bus",
    3: "others"
}


class VehicleDetector:
    """
    Wrapper for YOLOv8 model loading, inference, and bounding box extraction.
    Handles fallback from custom best.pt to pretrained yolov8n.pt.
    """
    def __init__(self, model_path: str = "models/yolov8n.pt", custom_path: str = "models/best.pt", conf_thresh: float = 0.40):
        self.conf_thresh = conf_thresh
        self.model_path = model_path
        self.custom_path = custom_path
        self.model = None
        self.model_status: str = "Uninitialized"
        self.is_custom: bool = False
        self.class_map = COCO_VEHICLE_MAP

        self.load_model()

    def load_model(self):
        try:
            from ultralytics import YOLO

            custom_file = Path(self.custom_path)
            if custom_file.exists() and custom_file.stat().st_size > 1000:
                print(f"[Detector] Loading custom trained model: {custom_file}")
                self.model = YOLO(str(custom_file))
                self.model_status = "Custom UA-DETRAC model loaded (best.pt)"
                self.is_custom = True
                self.class_map = DETRAC_CLASS_MAP
            else:
                base_file = Path(self.model_path)
                print(f"[Detector] Loading standard model: {base_file}")
                self.model = YOLO(str(base_file) if base_file.exists() else "yolov8n.pt")
                self.model_status = "Pretrained YOLOv8n loaded (Not fine-tuned)"
                self.is_custom = False
                self.class_map = COCO_VEHICLE_MAP
        except Exception as e:
            self.model_status = f"Error loading YOLO: {str(e)}"
            print(f"[Detector] {self.model_status}")

    def detect(self, frame: np.ndarray, conf: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Runs YOLO detection on frame.
        Returns list of detected vehicles:
        [{ 'bbox': [x1, y1, x2, y2], 'class_id': int, 'class_name': str, 'confidence': float, 'center': (cx, cy) }]
        """
        if self.model is None:
            return []

        active_conf = conf if conf is not None else self.conf_thresh
        target_classes = list(self.class_map.keys())

        try:
            results = self.model(frame, conf=active_conf, classes=target_classes, imgsz=1280, verbose=False)
            detections = []
            if not results or len(results) == 0:
                return []

            boxes = results[0].boxes
            if boxes is None or len(boxes) == 0:
                return []

            for box in boxes:
                coords = box.xyxy[0].tolist()
                x1, y1, x2, y2 = map(int, coords)
                conf_val = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = self.class_map.get(cls_id, results[0].names.get(cls_id, "vehicle"))
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)

                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "class_id": cls_id,
                    "class_name": cls_name,
                    "confidence": round(conf_val, 2),
                    "center": (cx, cy)
                })
            return detections
        except Exception as e:
            print(f"[Detector Detect Error] {e}")
            return []
