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

# Dedicated Mapping for Future Fine-Tuned Emergency Vehicle Model
# Target classes: ambulance, fire_truck, police
EMERGENCY_CLASS_MAP = {
    0: "ambulance",
    1: "fire_truck",
    2: "police"
}

# Exact names from the Indian Roboflow set. Ignore lamps/text/symbols.
EMERGENCY_NAME_ALIASES = {
    "ambulance": "ambulance",
    "ambulance_108": "ambulance",
    "ambulance_sol": "ambulance",
    "fire_truck": "fire_truck",
    "fireladder": "fire_truck",
    "police": "police",
}


class VehicleDetector:
    """
    Wrapper for YOLOv8 model loading, inference, and bounding box extraction.
    Handles fallback from custom best.pt to pretrained yolov8n.pt.
    Also provides a modular plug-in architecture for a dedicated emergency vehicle model.
    """
    def __init__(
        self,
        model_path: str = "models/yolov8n.pt",
        custom_path: str = "models/best.pt",
        conf_thresh: float = 0.40,
        emergency_model_path: Optional[str] = None,
        emergency_conf_thresh: float = 0.52
    ):
        self.conf_thresh = conf_thresh
        self.model_path = model_path
        self.custom_path = custom_path
        self.emergency_model_path = emergency_model_path or "models/emergency_colab_best.pt"
        self.emergency_conf_thresh = emergency_conf_thresh

        self.model = None
        self.model_status: str = "Uninitialized"
        self.is_custom: bool = False
        self.class_map = COCO_VEHICLE_MAP

        # Modular Emergency Detector state
        self.emergency_model = None
        self.has_emergency_model: bool = False
        self.emergency_model_status: str = "Uninitialized"

        self.load_model()
        self.load_emergency_model()

    def load_emergency_model(self):
        """
        Loads custom fine-tuned emergency vehicle weights if present on disk.
        Searches emergency_colab_best.pt and emergency_best.pt seamlessly.
        """
        try:
            from ultralytics import YOLO

            em_file = None
            if self.emergency_model_path:
                p = Path(self.emergency_model_path)
                if p.exists() and p.stat().st_size > 1000:
                    em_file = p

            # If not explicitly specified or using default names, search standard locations
            if em_file is None and (not self.emergency_model_path or Path(self.emergency_model_path).name in ("emergency_best.pt", "emergency_colab_best.pt")):
                root_models = Path(__file__).resolve().parent.parent.parent / "models"
                candidates = [
                    Path("models/emergency_colab_best.pt"),
                    Path("models/emergency_best.pt"),
                    root_models / "emergency_colab_best.pt",
                    root_models / "emergency_best.pt",
                ]
                for cand in candidates:
                    if cand.exists() and cand.stat().st_size > 1000:
                        em_file = cand
                        break

            if em_file is not None:
                self.emergency_model_path = str(em_file)
                print(f"[Detector] Loading custom emergency model: {em_file}")
                self.emergency_model = YOLO(str(em_file))
                self.emergency_model_status = f"Custom emergency model loaded ({em_file.name})"
                self.has_emergency_model = True

                # Dynamically resolve emergency classes from model's metadata
                self.active_emergency_map = {}
                if hasattr(self.emergency_model, "names") and self.emergency_model.names:
                    for cid, cname in self.emergency_model.names.items():
                        cn = str(cname).lower().strip()
                        if cn in EMERGENCY_NAME_ALIASES:
                            self.active_emergency_map[int(cid)] = EMERGENCY_NAME_ALIASES[cn]
                            continue
                        if "ambulance" in cn:
                            self.active_emergency_map[int(cid)] = "ambulance"
                        elif "fire" in cn:
                            self.active_emergency_map[int(cid)] = "fire_truck"
                        elif "police" in cn:
                            self.active_emergency_map[int(cid)] = "police"
                if not self.active_emergency_map:
                    self.active_emergency_map = dict(EMERGENCY_CLASS_MAP)
            else:
                self.emergency_model = None
                self.has_emergency_model = False
                self.active_emergency_map = dict(EMERGENCY_CLASS_MAP)
                self.emergency_model_status = (
                    f"Modular emergency architecture ready (Awaiting fine-tuned model at {self.emergency_model_path})"
                )
        except Exception as e:
            self.emergency_model_status = f"Error loading emergency model: {str(e)}"
            self.has_emergency_model = False
            self.active_emergency_map = dict(EMERGENCY_CLASS_MAP)
            print(f"[Detector] {self.emergency_model_status}")

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
            results = self.model(frame, conf=active_conf, classes=target_classes, imgsz=480, verbose=False)
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

    def detect_emergency(self, frame: np.ndarray, conf: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Runs modular emergency vehicle inference on frame if a fine-tuned model is present.
        Returns empty list when no custom emergency model is loaded (never fabricates detections).
        Output format:
        [{ 'bbox': [x1, y1, x2, y2], 'class_id': int, 'class_name': str, 'confidence': float, 'center': (cx, cy) }]
        Target classes: 'ambulance', 'fire_truck', 'police'
        """
        if self.emergency_model is None or not self.has_emergency_model:
            return []

        active_conf = conf if conf is not None else self.emergency_conf_thresh
        active_map = getattr(self, "active_emergency_map", EMERGENCY_CLASS_MAP)
        target_classes = list(active_map.keys())

        try:
            results = self.emergency_model(frame, conf=active_conf, iou=0.45, classes=target_classes, imgsz=480, verbose=False)
            if not results or len(results) == 0:
                return []
            boxes = results[0].boxes
            if boxes is None or len(boxes) == 0:
                return []

            emergency_detections = []
            for box in boxes:
                coords = box.xyxy[0].tolist()
                x1, y1, x2, y2 = map(int, coords)
                conf_val = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = active_map.get(cls_id, results[0].names.get(cls_id, "emergency"))
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)

                bw = x2 - x1
                bh = y2 - y1
                # Reject noise, specks, and extreme non-vehicle aspect ratios (e.g. guardrail glare slivers)
                if bw < 35 or bh < 35:
                    continue
                aspect = bw / float(bh)
                if aspect > 3.2 or aspect < 0.28:
                    continue

                emergency_detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "class_id": cls_id,
                    "class_name": cls_name,
                    "confidence": round(conf_val, 2),
                    "center": (cx, cy)
                })
            return emergency_detections
        except Exception as e:
            print(f"[Emergency Detector Error] {e}")
            return []

    def get_status_summary(self) -> Dict[str, Any]:
        """Provides status summary for model APIs and telemetry."""
        return {
            "primary_model_status": self.model_status,
            "primary_model_path": self.model_path,
            "is_custom_primary": self.is_custom,
            "emergency_model_status": self.emergency_model_status,
            "emergency_model_path": self.emergency_model_path,
            "has_emergency_model": self.has_emergency_model,
            "emergency_classes": list(EMERGENCY_CLASS_MAP.values())
        }

