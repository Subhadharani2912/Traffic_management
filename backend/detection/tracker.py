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

        # Dedicated Emergency Vehicle Attributes (Phase 2)
        self.emergency_type: Optional[str] = None  # 'ambulance', 'fire_truck', 'police'
        self.emergency_confidence: float = 0.0
        self.emergency_detected: bool = False
        self.emergency_detection_frames: int = 0
        self.emergency_direction: Optional[str] = None
        self.emergency_active: bool = False
        self.preemption_triggered: bool = False

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
            if self.direction:
                self.emergency_direction = self.direction

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

    def update_emergency(
        self,
        is_detected: bool,
        emergency_type: Optional[str] = None,
        confidence: float = 0.0,
        confirmation_frames: int = 5
    ) -> bool:
        """
        Updates multi-frame temporal confirmation for emergency vehicles.
        Emergency detection must persist for at least `confirmation_frames`
        consecutive frames before `emergency_active` is set to True.
        Returns True if the vehicle just transitioned to confirmed active state.
        """
        became_active = False
        valid_types = {"ambulance", "fire_truck", "police"}
        if is_detected and emergency_type in valid_types:
            self.emergency_detected = True
            self.emergency_type = emergency_type
            self.emergency_confidence = confidence
            if not self.emergency_direction and self.direction:
                self.emergency_direction = self.direction
            self.emergency_detection_frames += 1

            if self.emergency_detection_frames >= confirmation_frames:
                if not self.emergency_active:
                    became_active = True
                self.emergency_active = True
        else:
            self.emergency_detected = False
            self.emergency_detection_frames = 0
            self.emergency_active = False
            self.emergency_type = None
            self.emergency_confidence = 0.0

        return became_active

    def to_dict(self) -> Dict[str, Any]:
        is_em = bool(self.emergency_active or (self.emergency_detected and self.emergency_detection_frames >= 3 and self.emergency_confidence >= 0.50))
        display_class = self.emergency_type if is_em else self.class_name
        display_direction = self.emergency_direction or self.direction or "UNKNOWN"

        if is_em:
            self.signal_blocked = False
            if self.emergency_active:
                status = f"EMERGENCY ({self.emergency_type.upper() if self.emergency_type else 'AMBULANCE'})"
            else:
                status = f"DETECTING {self.emergency_type.upper() if self.emergency_type else 'AMBULANCE'}"
        elif self.signal_blocked:
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
            "class": display_class,
            "confidence": round(self.confidence, 2),
            "bbox": self.bbox,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "direction": display_direction,
            "speed": round(self.speed, 1),
            "waiting_time": round(self.waiting_time, 1),
            "in_intersection": self.in_intersection,
            "has_crossed": self.has_crossed,
            "stopped": self.signal_blocked and not is_em,
            "ran_red": self.ran_red and not is_em,
            "crossed_signal": self.crossed_signal or "GREEN",
            "status": status,
            # Emergency Vehicle Fields
            "is_emergency": is_em,
            "emergency_type": self.emergency_type,
            "emergency_confidence": round(self.emergency_confidence, 2),
            "emergency_detected": self.emergency_detected,
            "emergency_detection_frames": self.emergency_detection_frames,
            "emergency_direction": self.emergency_direction,
            "emergency_active": self.emergency_active
        }


class VehicleTrackerManager:
    """
    Manages active vehicle tracks, associates YOLO track IDs or centroid distances,
    applies multi-frame temporal emergency confirmation, and removes inactive tracks.
    """
    def __init__(self, max_missing_frames: int = 15, emergency_confirmation_frames: int = 5):
        self.vehicles: Dict[int, TrackedVehicle] = {}
        self.max_missing_frames = max_missing_frames
        self.emergency_confirmation_frames = emergency_confirmation_frames
        self.next_auto_id = 1

    def update_with_yolo_tracks(
        self,
        yolo_results,
        lane_manager: LaneManager,
        width: int,
        height: int,
        timestamp: float,
        signal_states: Optional[Dict[str, str]] = None,
        boxes: Optional[List[Dict[str, Any]]] = None,
        emergency_detections: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Updates tracked vehicles using Ultralytics YOLO track output (boxes with .id),
        or from pre-made box entries (e.g. virtual demo detections).
        Associates emergency detections with vehicles and applies multi-frame confirmation.
        """
        active_ids = set()

        entries = []
        if boxes is not None:
            # Pre-made detections: [{bbox:[x1,y1,x2,y2], conf, cls, id, (optional emergency_type)}]
            for bx in boxes:
                conf = float(bx.get("conf", 0.9))
                cls_name = str(bx.get("cls", "car"))
                track_id = bx.get("id")
                if track_id is None:
                    track_id = self._match_or_create(list(map(int, bx["bbox"])), cls_name, conf, timestamp)
                entries.append((list(map(int, bx["bbox"])), conf, cls_name, track_id, bx.get("emergency_type")))
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
                entries.append((bbox, conf, cls_name, track_id, None))

        for item in entries:
            bbox, conf, cls_name, track_id = item[0], item[1], item[2], item[3]
            entry_em_type = item[4] if len(item) > 4 else None
            active_ids.add(track_id)

            if track_id in self.vehicles:
                self.vehicles[track_id].update(bbox, conf, timestamp, lane_manager, width, height, signal_states)
            else:
                veh = TrackedVehicle(track_id, cls_name, bbox, conf, timestamp)
                veh.direction = lane_manager.classify_direction(veh.center_x, veh.center_y, width, height)
                veh.emergency_direction = veh.direction
                veh.in_intersection = lane_manager.is_in_intersection(veh.center_x, veh.center_y, width, height)
                if signal_states is not None:
                    sig = signal_states.get(veh.direction, "GREEN") if veh.direction else "GREEN"
                    veh.signal_blocked = sig in ("RED", "YELLOW") and not veh.in_intersection
                    if veh.signal_blocked:
                        veh.speed = 0.0
                self.vehicles[track_id] = veh

            # If the detection entry explicitly tags an emergency type (e.g. test boxes)
            if entry_em_type in ("ambulance", "fire_truck", "police"):
                self.vehicles[track_id].update_emergency(
                    True, entry_em_type, conf, self.emergency_confirmation_frames
                )

        # Associate external emergency detector outputs if provided
        if emergency_detections:
            # Secondary NMS deduplication to avoid multiple tracks for the same emergency vehicle
            cleaned_em_dets = []
            for em in sorted(emergency_detections, key=lambda x: x.get("confidence", 0.0), reverse=True):
                b = em.get("bbox")
                if not b:
                    continue
                overlap = False
                for existing in cleaned_em_dets:
                    eb = existing["bbox"]
                    ix1 = max(b[0], eb[0])
                    iy1 = max(b[1], eb[1])
                    ix2 = min(b[2], eb[2])
                    iy2 = min(b[3], eb[3])
                    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                    union = (b[2] - b[0]) * (b[3] - b[1]) + (eb[2] - eb[0]) * (eb[3] - eb[1]) - inter
                    iou = inter / union if union > 0 else 0.0
                    if iou > 0.30:
                        overlap = True
                        break
                if not overlap:
                    cleaned_em_dets.append(em)

            matched_vids = set()
            for em_det in cleaned_em_dets:
                em_cx, em_cy = em_det.get("center", (0, 0))
                em_type = em_det.get("class_name", "ambulance")
                em_conf = em_det.get("confidence", 0.9)
                bbox = em_det.get("bbox")

                best_vid = None
                best_iou = 0.0
                best_dist = 180.0
                for vid, veh in self.vehicles.items():
                    iou = 0.0
                    if bbox and veh.bbox:
                        ix1 = max(bbox[0], veh.bbox[0])
                        iy1 = max(bbox[1], veh.bbox[1])
                        ix2 = min(bbox[2], veh.bbox[2])
                        iy2 = min(bbox[3], veh.bbox[3])
                        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                        union = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) + (veh.bbox[2] - veh.bbox[0]) * (veh.bbox[3] - veh.bbox[1]) - inter
                        iou = inter / union if union > 0 else 0.0
                    dist = math.hypot(veh.center_x - em_cx, veh.center_y - em_cy)
                    if iou > 0.20 and iou > best_iou:
                        best_iou = iou
                        best_vid = vid
                    elif best_vid is None and dist < best_dist:
                        best_vid = vid

                if best_vid is not None:
                    matched_vids.add(best_vid)
                    active_ids.add(best_vid)
                    if bbox and best_vid not in [e[3] for e in entries]:
                        self.vehicles[best_vid].update(bbox, em_conf, timestamp, lane_manager, width, height, signal_states)
                    if not self.vehicles[best_vid].emergency_direction:
                        self.vehicles[best_vid].emergency_direction = (
                            self.vehicles[best_vid].direction or
                            lane_manager.classify_direction(em_cx, em_cy, width, height, fallback_nearest=True)
                        )
                    became_em = self.vehicles[best_vid].update_emergency(
                        True, em_type, em_conf, self.emergency_confirmation_frames
                    )
                    if became_em or self.vehicles[best_vid].emergency_active:
                        self.vehicles[best_vid].class_name = em_type
                        self.vehicles[best_vid].signal_blocked = False
                elif bbox:
                    # Check if overlaps with any vehicle in active_ids to avoid creating a second duplicate track
                    is_dup = False
                    for existing_vid in active_ids:
                        eveh = self.vehicles.get(existing_vid)
                        if eveh and eveh.bbox:
                            ix1 = max(bbox[0], eveh.bbox[0])
                            iy1 = max(bbox[1], eveh.bbox[1])
                            ix2 = min(bbox[2], eveh.bbox[2])
                            iy2 = min(bbox[3], eveh.bbox[3])
                            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                            union = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) + (eveh.bbox[2] - eveh.bbox[0]) * (eveh.bbox[3] - eveh.bbox[1]) - inter
                            if union > 0 and (inter / union) > 0.25:
                                became_em = eveh.update_emergency(True, em_type, em_conf, self.emergency_confirmation_frames)
                                if became_em or eveh.emergency_active:
                                    eveh.class_name = em_type
                                    eveh.signal_blocked = False
                                matched_vids.add(existing_vid)
                                is_dup = True
                                break
                    if not is_dup:
                        new_vid = self.next_auto_id
                        self.next_auto_id += 1
                        active_ids.add(new_vid)
                        matched_vids.add(new_vid)
                        veh = TrackedVehicle(new_vid, em_type, bbox, em_conf, timestamp)
                        veh.direction = lane_manager.classify_direction(veh.center_x, veh.center_y, width, height, fallback_nearest=True)
                        veh.emergency_direction = veh.direction
                        veh.in_intersection = lane_manager.is_in_intersection(veh.center_x, veh.center_y, width, height)
                        veh.signal_blocked = False
                        self.vehicles[new_vid] = veh
                        self.vehicles[new_vid].update_emergency(
                            True, em_type, em_conf, self.emergency_confirmation_frames
                        )

            # For active vehicles not matched with emergency detection in this frame, reset
            for vid in active_ids:
                if vid not in matched_vids and not any(e[3] == vid and e[4] for e in entries):
                    self.vehicles[vid].update_emergency(False, None, 0.0, self.emergency_confirmation_frames)

        # Increment missing frames for unseen vehicles
        to_delete = []
        for vid, veh in self.vehicles.items():
            if vid not in active_ids:
                veh.frames_missing += 1
                if veh.frames_missing > self.max_missing_frames:
                    to_delete.append(vid)

        for vid in to_delete:
            del self.vehicles[vid]

        # Only return active vehicles seen in the current frame (frames_missing == 0)
        # This completely stops ghost boxes and overlapping old frames from polluting the screen
        return [v.to_dict() for v in self.vehicles.values() if v.frames_missing == 0]

    def get_active_emergency(self) -> Optional[TrackedVehicle]:
        """Returns the first active, confirmed emergency vehicle approaching the intersection."""
        for veh in self.vehicles.values():
            if veh.emergency_active and not veh.has_crossed and (veh.direction or veh.emergency_direction):
                return veh
        return None

    def simulate_emergency_step(
        self,
        track_id: int,
        direction: str,
        emergency_type: str = "ambulance",
        confidence: float = 0.95
    ) -> TrackedVehicle:
        """
        Helper for unit tests / simulation: steps an emergency vehicle detection
        for a given track ID and updates its temporal confirmation frames.
        """
        if track_id not in self.vehicles:
            veh = TrackedVehicle(track_id, "car", [100, 100, 200, 200], confidence, time.time())
            veh.direction = direction
            veh.emergency_direction = direction
            self.vehicles[track_id] = veh
        veh = self.vehicles[track_id]
        veh.direction = direction
        veh.emergency_direction = direction
        veh.update_emergency(True, emergency_type, confidence, self.emergency_confirmation_frames)
        return veh

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
