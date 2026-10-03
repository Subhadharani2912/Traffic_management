import time
import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from backend.traffic.lane_manager import LaneManager


class TrackedVehicle:
    def __init__(self, track_id: int, class_name: str, bbox: List[int], confidence: float, timestamp: float):
        self.id = track_id
        self.class_name = class_name
        self.bbox = bbox  # [x1, y1, x2, y2]
        self.confidence = confidence
        self.center_x = (bbox[0] + bbox[2]) // 2
        self.center_y = (bbox[1] + bbox[3]) // 2

        self.first_seen = timestamp
        self.last_seen = timestamp
        self.frames_missing = 0

        self.speed = 0.0  # pixels per second
        self.history: List[Tuple[int, int, float]] = [(self.center_x, self.center_y, timestamp)]

        self.direction: Optional[str] = None
        self.in_intersection: bool = False
        self.has_crossed: bool = False
        self.counted_as_passed: bool = False
        self.waiting_time: float = 0.0
        self.signal_blocked: bool = False
        self.ran_red: bool = False
        self.crossed_signal: Optional[str] = None

    def update(self, bbox: List[int], confidence: float, timestamp: float, lane_manager: LaneManager, width: int, height: int, signal_states: Optional[Dict[str, str]] = None):
        new_cx = (bbox[0] + bbox[2]) // 2
        new_cy = (bbox[1] + bbox[3]) // 2
        dt = max(0.001, timestamp - self.last_seen)

        # Calculate speed (pixels / sec)
        dist = math.hypot(new_cx - self.center_x, new_cy - self.center_y)
        current_speed = dist / dt
        # Smooth speed
        self.speed = 0.7 * self.speed + 0.3 * current_speed

        self.bbox = bbox
        self.confidence = confidence
        self.center_x = new_cx
        self.center_y = new_cy
        self.last_seen = timestamp
        self.frames_missing = 0

        self.history.append((new_cx, new_cy, timestamp))
        if len(self.history) > 30:
            self.history.pop(0)

        # Update intersection & lane status
        was_in_roi = (self.direction is not None)
        in_center = lane_manager.is_in_intersection(new_cx, new_cy, width, height)

        if self.direction is None:
            self.direction = lane_manager.classify_direction(new_cx, new_cy, width, height)

        if in_center:
            self.in_intersection = True

        # Check if crossed: was in approach ROI, passed through intersection and now moving away
        if self.in_intersection and not in_center and was_in_roi:
            self.has_crossed = True
            self.in_intersection = False

        if signal_states is None:
            signal_states = {}
        sig = signal_states.get(self.direction, "GREEN") if self.direction else "GREEN"
        if self.has_crossed and self.crossed_signal is None:
            self.crossed_signal = sig
            self.ran_red = sig != "GREEN"
        self.signal_blocked = sig in ("RED", "YELLOW") and not self.in_intersection and not self.has_crossed
        if self.signal_blocked:
            self.speed = 0.0

    def to_dict(self) -> Dict[str, Any]:
        if self.signal_blocked:
            status = "STOPPED"
        elif self.ran_red:
            status = "VIOLATION"
        elif self.in_intersection:
            status = "Crossing"
        elif self.has_crossed:
            status = "Passed"
        elif self.waiting_time > 0.5:
            status = "Waiting"
        else:
            status = "Approaching"
        return {
            "id": self.id,
            "class": self.class_name,
            "confidence": round(self.confidence, 2),
            "bbox": self.bbox,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "direction": self.direction or "UNKNOWN",
            "speed": round(self.speed, 1),
            "waiting_time": round(self.waiting_time, 1),
            "in_intersection": self.in_intersection,
            "has_crossed": self.has_crossed,
            "stopped": self.signal_blocked,
            "ran_red": self.ran_red,
            "crossed_signal": self.crossed_signal or "GREEN",
            "status": status
        }


class VehicleTrackerManager:
    """
    Manages active vehicle tracks, associates YOLO track IDs or centroid distances,
    and removes inactive tracks.
    """
    def __init__(self, max_missing_frames: int = 15):
        self.vehicles: Dict[int, TrackedVehicle] = {}
        self.max_missing_frames = max_missing_frames
        self.next_auto_id = 1

    def update_with_yolo_tracks(
        self,
        yolo_results,
        lane_manager: LaneManager,
        width: int,
        height: int,
        timestamp: float,
        signal_states: Optional[Dict[str, str]] = None,
        boxes: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Updates tracked vehicles using Ultralytics YOLO track output (boxes with .id),
        or from pre-made box entries (e.g. virtual demo detections).
        """
        active_ids = set()

        entries = []
        if boxes is not None:
            # Pre-made detections: [{bbox:[x1,y1,x2,y2], conf, cls, id}]
            for bx in boxes:
                conf = float(bx.get("conf", 0.9))
                cls_name = str(bx.get("cls", "car"))
                track_id = bx.get("id")
                if track_id is None:
                    track_id = self._match_or_create(list(map(int, bx["bbox"])), cls_name, conf, timestamp)
                entries.append((list(map(int, bx["bbox"])), conf, cls_name, track_id))
        elif yolo_results and len(yolo_results) > 0 and yolo_results[0].boxes is not None:
            for box in yolo_results[0].boxes:
                coords = box.xyxy[0].tolist()
                bbox = list(map(int, coords))
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = yolo_results[0].names.get(cls_id, "vehicle")

                # If ByteTrack assigned track id
                if box.id is not None:
                    track_id = int(box.id[0])
                else:
                    # Match nearest or allocate
                    track_id = self._match_or_create(bbox, cls_name, conf, timestamp)
                entries.append((bbox, conf, cls_name, track_id))

        for bbox, conf, cls_name, track_id in entries:
            active_ids.add(track_id)

            if track_id in self.vehicles:
                self.vehicles[track_id].update(bbox, conf, timestamp, lane_manager, width, height, signal_states)
            else:
                veh = TrackedVehicle(track_id, cls_name, bbox, conf, timestamp)
                veh.direction = lane_manager.classify_direction(veh.center_x, veh.center_y, width, height)
                veh.in_intersection = lane_manager.is_in_intersection(veh.center_x, veh.center_y, width, height)
                if signal_states is not None:
                    sig = signal_states.get(veh.direction, "GREEN") if veh.direction else "GREEN"
                    veh.signal_blocked = sig in ("RED", "YELLOW") and not veh.in_intersection
                    if veh.signal_blocked:
                        veh.speed = 0.0
                self.vehicles[track_id] = veh

        # Increment missing frames for unseen vehicles
        to_delete = []
        for vid, veh in self.vehicles.items():
            if vid not in active_ids:
                veh.frames_missing += 1
                if veh.frames_missing > self.max_missing_frames:
                    to_delete.append(vid)

        for vid in to_delete:
            del self.vehicles[vid]

        return [v.to_dict() for v in self.vehicles.values()]

    def _match_or_create(self, bbox: List[int], cls_name: str, conf: float, timestamp: float) -> int:
        cx = (bbox[0] + bbox[2]) // 2
        cy = (bbox[1] + bbox[3]) // 2

        best_id = None
        min_dist = 60.0  # max association distance in pixels

        for vid, veh in self.vehicles.items():
            if veh.frames_missing > 0:
                dist = math.hypot(veh.center_x - cx, veh.center_y - cy)
                if dist < min_dist:
                    min_dist = dist
                    best_id = vid

        if best_id is not None:
            return best_id

        new_id = self.next_auto_id
        self.next_auto_id += 1
        return new_id
