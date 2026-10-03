import cv2
import time
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Generator, Tuple, List
import numpy as np

from backend.config import TrafficSystemConfig, VIDEOS_INPUT_DIR, VIDEOS_OUTPUT_DIR
from backend.detection.detector import VehicleDetector
from backend.detection.tracker import VehicleTrackerManager
from backend.traffic.lane_manager import LaneManager
from backend.traffic.vehicle_counter import VehicleCounter
from backend.traffic.density import DensityCalculator
from backend.traffic.waiting_time import WaitingTimeTracker
from backend.traffic.priority import PriorityCalculator
from backend.traffic.signal_controller import SignalController
from backend.database.database import record_traffic_metric, record_phase_switch, log_event


class VideoProcessorService:
    """
    Asynchronous Video Processing Service for Live Traffic Analysis (Mode 1).
    Processes video frame-by-frame with YOLO detection, ByteTrack tracking,
    ROI classification, and adaptive signal timing.
    """
    def __init__(self, config: TrafficSystemConfig, detector: Optional[VehicleDetector] = None):
        self.config = config
        self.detector = detector or VehicleDetector(
            model_path=config.model_path,
            custom_path=config.custom_model_path,
            conf_thresh=config.confidence_threshold
        )
        self.tracker = VehicleTrackerManager()
        self.lane_manager = LaneManager(config.rois, config.intersection_box)
        self.counter = VehicleCounter()
        self.density_calc = DensityCalculator(
            low_max=config.density_low_max,
            med_max=config.density_medium_max,
            max_capacity=25
        )
        self.wait_tracker = WaitingTimeTracker(speed_threshold=config.waiting_speed_threshold)
        self.priority_calc = PriorityCalculator(
            density_weight=config.density_weight,
            waiting_weight=config.waiting_weight,
            starvation_threshold=config.starvation_threshold_seconds,
            min_green=config.min_green_time,
            max_green=config.max_green_time,
            headway_seconds=config.headway_seconds,
            start_window_seconds=config.start_window_seconds
        )
        self.signal_controller = SignalController(
            priority_calc=self.priority_calc,
            yellow_duration=config.yellow_time,
            all_red_duration=config.all_red_time,
            adaptive_mode=config.adaptive_mode
        )

        self.cap: Optional[cv2.VideoCapture] = None
        self.current_video_path: Optional[str] = None
        self.is_running = False
        self.is_paused = False
        self.thread: Optional[threading.Thread] = None

        self.latest_frame: Optional[np.ndarray] = None
        self.latest_state: Dict[str, Any] = {}
        self.fps_actual: float = 0.0
        self.current_session_id: Optional[int] = None
        self.lock = threading.Lock()

        # Connect signal controller callback to database logging
        self.signal_controller.set_callback(self._on_phase_switch)

        # Per-direction frozen buffers for pixel-level signal gating
        # Each entry: {"buf": np.ndarray or None, "alpha": float}
        self._freeze_buffers: Dict[str, Dict[str, Any]] = {
            d: {"buf": None, "alpha": 0.0} for d in ["NORTH", "SOUTH", "EAST", "WEST"]
        }

        # Virtual demo detections (sidecar <video>.json with per-frame boxes).
        # Lets a synthetic demo video drive density + waiting time signals without YOLO.
        self.virtual_frames: List[List[Dict[str, Any]]] = []
        self._vfreeze: Dict[str, Optional[List[Dict[str, Any]]]] = {
            d: None for d in ["NORTH", "SOUTH", "EAST", "WEST"]
        }
        self._frame_index = 0

    def _on_phase_switch(self, direction, from_st, to_st, duration, count, priority):
        log_event(
            f"Signal {direction}: {from_st} -> {to_st} (Assigned: {duration:.1f}s, Vehicles: {count}, Pri: {priority:.1f})",
            "INFO", "SIGNAL"
        )
        if self.current_session_id:
            record_phase_switch(self.current_session_id, {
                "phase_direction": direction,
                "from_state": from_st,
                "to_state": to_st,
                "duration_assigned": duration,
                "vehicle_count": count,
                "priority_score": priority
            })

    def start(self, video_path: str, session_id: Optional[int] = None):
        self.stop()
        self.current_video_path = video_path
        self.current_session_id = session_id
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            log_event(f"Failed to open video file: {video_path}", "ERROR", "VIDEO")
            return False

        # Load virtual demo detections if a sidecar .json exists next to the video
        self.virtual_frames = []
        sidecar = Path(video_path).with_suffix(".json")
        if sidecar.exists():
            try:
                with open(sidecar, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.virtual_frames = data.get("frames", []) if isinstance(data, dict) else data
                log_event(f"Virtual demo detections loaded: {len(self.virtual_frames)} frames", "INFO", "VIDEO")
            except Exception as e:
                log_event(f"Failed to load virtual demo {sidecar}: {e}", "WARNING", "VIDEO")
        self._frame_index = 0
        self._vfreeze = {d: None for d in ["NORTH", "SOUTH", "EAST", "WEST"]}

        self.is_running = True
        self.is_paused = False
        self.thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.thread.start()
        log_event(f"Video processing started: {Path(video_path).name}", "INFO", "VIDEO")
        return True

    def pause(self):
        self.is_paused = not self.is_paused
        return self.is_paused

    def stop(self):
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
            self.cap = None

    def _processing_loop(self):
        fps_target = self.config.processing_fps or 15
        delay = 1.0 / max(1, fps_target)
        last_metric_save = time.time()

        while self.is_running:
            if self.is_paused:
                time.sleep(0.1)
                continue

            t0 = time.time()
            ret, frame = self.cap.read()
            if not ret:
                # Video loop or completion
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self._frame_index = 0
                ret, frame = self.cap.read()
                if not ret:
                    break
            self._frame_index += 1

            h, w = frame.shape[:2]
            current_time = time.time()

            # 1. Build detections: virtual demo boxes (signal-gated) or YOLO track
            signal_states = self.signal_controller.get_signal_states()
            virt_boxes = self._virtual_boxes_for_frame(signal_states)
            if virt_boxes is not None:
                tracked_vehicles = self.tracker.update_with_yolo_tracks(
                    None, self.lane_manager, w, h, current_time, signal_states, boxes=virt_boxes
                )
            else:
                tracked_vehicles = self._track_real_frame(frame, w, h, current_time, signal_states)

            # 3. Vehicle counting & density
            counts = self.counter.update_from_tracked_vehicles(tracked_vehicles)
            densities = self.density_calc.update(counts)

            # 4. Waiting time calculation
            sig_states = self.signal_controller.get_signal_states()
            dt = max(0.01, time.time() - t0)
            waiting_stats = self.wait_tracker.update(tracked_vehicles, sig_states, dt)

            # 5. Signal controller step
            ctrl_state = self.signal_controller.step(dt, counts, waiting_stats)

            # 6. Pixel-gate approaches by signal (vehicles visually stop on RED/YELLOW, move on GREEN)
            gated_frame = self._apply_signal_gate(frame, ctrl_state["signal_states"], dt)

            # 7. Render overlay
            annotated_frame = self._draw_overlays(gated_frame, tracked_vehicles, ctrl_state, counts, densities, waiting_stats, w, h)

            # Calculate FPS
            elapsed = time.time() - t0
            self.fps_actual = round(1.0 / max(elapsed, 0.001), 1)

            # Periodic metric recording in SQLite (every 3 seconds)
            if self.current_session_id and (time.time() - last_metric_save > 3.0):
                last_metric_save = time.time()
                record_traffic_metric(self.current_session_id, {
                    "north_count": counts.get("NORTH", 0),
                    "south_count": counts.get("SOUTH", 0),
                    "east_count": counts.get("EAST", 0),
                    "west_count": counts.get("WEST", 0),
                    "north_density": densities.get("NORTH", ("LOW", 0))[0],
                    "south_density": densities.get("SOUTH", ("LOW", 0))[0],
                    "east_density": densities.get("EAST", ("LOW", 0))[0],
                    "west_density": densities.get("WEST", ("LOW", 0))[0],
                    "north_wait": waiting_stats.get("NORTH", {}).get("avg_wait", 0.0),
                    "south_wait": waiting_stats.get("SOUTH", {}).get("avg_wait", 0.0),
                    "east_wait": waiting_stats.get("EAST", {}).get("avg_wait", 0.0),
                    "west_wait": waiting_stats.get("WEST", {}).get("avg_wait", 0.0),
                    "current_green": ctrl_state["current_direction"],
                    "green_duration": int(ctrl_state["current_green_duration"]),
                    "priority_scores": ctrl_state["priorities"]
                })

            # Format current state for API & WebSocket
            directions_summary = {}
            for d in ["NORTH", "SOUTH", "EAST", "WEST"]:
                d_level, d_pct = densities.get(d, ("LOW", 0.0))
                w_info = waiting_stats.get(d, {})
                directions_summary[d] = {
                    "direction": d,
                    "count": counts.get(d, 0),
                    "waiting_count": w_info.get("wait_count", 0),
                    "density_level": d_level,
                    "density_percent": d_pct,
                    "avg_waiting_time": w_info.get("avg_wait", 0.0),
                    "max_waiting_time": w_info.get("max_wait", 0.0),
                    "signal_state": ctrl_state["signal_states"].get(d, "RED"),
                    "priority_score": ctrl_state["priorities"].get(d, 0.0),
                    "starvation_timer": w_info.get("starvation_timer", 0.0)
                }

            all_waits = [w.get("avg_wait", 0.0) for w in waiting_stats.values() if w.get("avg_wait", 0.0) > 0]
            sys_avg_wait = sum(all_waits) / len(all_waits) if all_waits else 0.0
            sys_max_wait = max([w.get("max_wait", 0.0) for w in waiting_stats.values()], default=0.0)

            state = {
                "mode": "video",
                "active_direction": ctrl_state["current_direction"],
                "active_signal_state": ctrl_state["phase_state"],
                "current_green_time_assigned": ctrl_state["current_green_duration"],
                "remaining_green_time": ctrl_state["timer_remaining"],
                "yellow_remaining": ctrl_state["timer_remaining"] if ctrl_state["phase_state"] == "YELLOW" else 0.0,
                "next_direction": ctrl_state["next_direction"],
                "next_priority_score": ctrl_state["next_priority_score"],
                "total_active_vehicles": self.counter.get_total_active(),
                "total_waiting_vehicles": sum(
                    w_info.get("wait_count", 0) for w_info in waiting_stats.values()
                ),
                "total_passed_vehicles": self.counter.get_total_passed(),
                "system_avg_waiting_time": round(sys_avg_wait, 1),
                "system_max_waiting_time": round(sys_max_wait, 1),
                "fps": self.fps_actual,
                "adaptive_mode": self.signal_controller.adaptive_mode,
                "directions": directions_summary,
                "tracked_vehicles": tracked_vehicles,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            with self.lock:
                self.latest_frame = annotated_frame
                self.latest_state = state

            # Sleep to match target FPS
            proc_time = time.time() - t0
            sleep_time = max(0.001, delay - proc_time)
            time.sleep(sleep_time)

    def _track_real_frame(self, frame, w, h, current_time, signal_states):
        """YOLO ByteTrack with a resilient fallback to plain detection + centroid association."""
        results = None
        try:
            results = self.detector.model.track(
                frame,
                conf=self.config.confidence_threshold,
                iou=self.config.iou_threshold,
                persist=True,
                classes=list(self.detector.class_map.keys()),
                imgsz=1280,
                verbose=False
            )
        except Exception as e:
            log_event(f"model.track failed, using detector.detect: {e}", "WARNING", "VIDEO")
        if results is not None and results and results[0].boxes is not None and len(results[0].boxes) > 0:
            return self.tracker.update_with_yolo_tracks(
                results, self.lane_manager, w, h, current_time, signal_states
            )
        try:
            det_blob = self.detector.detect(frame, conf=self.config.confidence_threshold)
            if det_blob:
                return self.tracker.update_with_yolo_tracks(
                    None, self.lane_manager, w, h, current_time, signal_states, boxes=[
                        {"bbox": d["bbox"], "conf": d["confidence"], "cls": d["class_name"], "id": None}
                        for d in det_blob
                    ]
                )
        except Exception as e2:
            log_event(f"detector.detect fallback failed: {e2}", "WARNING", "VIDEO")
        return self.tracker.update_with_yolo_tracks(None, self.lane_manager, w, h, current_time, signal_states)

    def _virtual_boxes_for_frame(self, signal_states: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
        """
        Returns the virtual demo boxes for the current frame, signal-gated:
        boxes in a RED/YELLOW direction are frozen at the positions they had
        when the signal turned restrictive (matching the pixel freeze), so the
        tracker sees stopped vehicles and waiting time accrues. GREEN directions
        use live positions.
        Returns None when no virtual demo is loaded (normal YOLO path).
        """
        if not self.virtual_frames:
            return None

        frames = self.virtual_frames
        idx = (self._frame_index - 1) % len(frames)
        raw = frames[idx]
        by_dir: Dict[str, List[Dict[str, Any]]] = {d: [] for d in ["NORTH", "SOUTH", "EAST", "WEST"]}
        for bx in raw:
            if bx.get("bbox"):
                d = bx.get("dir", "NORTH")
                by_dir.setdefault(d, []).append(bx)

        out: List[Dict[str, Any]] = []
        for d in ["NORTH", "SOUTH", "EAST", "WEST"]:
            st = signal_states.get(d, "RED")
            live = by_dir.get(d, [])
            if st in ("RED", "YELLOW"):
                if self._vfreeze.get(d) is None:
                    # snapshot positions at the moment the signal turned restrictive
                    self._vfreeze[d] = [dict(b) for b in live]
                out.extend(self._vfreeze[d])
            else:
                self._vfreeze[d] = None
                out.extend(live)

        return out

    def _apply_signal_gate(
        self,
        frame: np.ndarray,
        signal_states: Dict[str, str],
        dt: float
    ) -> np.ndarray:
        """
        Pixel-level traffic light enforcement.

        When a direction is RED/YELLOW, its approach region is frozen to the
        frame captured at the moment the signal turned (vehicles visually wait
        behind the stop line). When it turns GREEN the region blends back to the
        live feed so vehicles visibly move. The intersection core always stays
        live so clearing traffic keeps moving.
        """
        out = frame.copy()
        h, w = frame.shape[:2]

        ibox = self.lane_manager.get_pixel_box(self.lane_manager.intersection_box, w, h)
        ix1, iy1, ix2, iy2 = ibox

        for d in ["NORTH", "SOUTH", "EAST", "WEST"]:
            st = signal_states.get(d, "RED")
            entry = self._freeze_buffers.setdefault(d, {"buf": None, "alpha": 0.0})

            if st in ("RED", "YELLOW"):
                # Snapshot the moment the signal goes restrictive
                if entry["buf"] is None:
                    entry["buf"] = frame.copy()
                    entry["alpha"] = 1.0
            else:
                # GREEN: fade the frozen region back into the live feed
                if entry["buf"] is not None:
                    entry["alpha"] = max(0.0, entry["alpha"] - 2.5 * dt)
                    if entry["alpha"] <= 0.0:
                        entry["buf"] = None

            buf = entry["buf"]
            if buf is None:
                continue

            poly = self.lane_manager.get_pixel_polygon(self.lane_manager.rois[d], w, h)
            if len(poly) < 3:
                continue
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask, [np.array(poly, np.int32)], 255)

            live = cv2.bitwise_and(frame, frame, mask=mask).astype(np.float32)
            frozen = cv2.bitwise_and(buf, buf, mask=mask).astype(np.float32)
            blended = (entry["alpha"] * frozen + (1.0 - entry["alpha"]) * live).astype(np.uint8)
            out = cv2.copyTo(blended, mask, out)

        # Intersection core always from the live frame (clearing traffic continues)
        out[max(0, iy1):iy2, max(0, ix1):ix2] = frame[max(0, iy1):iy2, max(0, ix1):ix2]
        return out

    def _draw_overlays(
        self,
        frame: np.ndarray,
        tracked: list,
        ctrl: dict,
        counts: dict,
        densities: dict,
        wait_stats: dict,
        w: int,
        h: int
    ) -> np.ndarray:
        out = frame.copy()

        # 1. Draw 4 Direction ROIs (semi-transparent)
        overlay = out.copy()
        for direction, box in self.lane_manager.rois.items():
            poly = self.lane_manager.get_pixel_polygon(box, w, h)
            if len(poly) < 3:
                continue
            pts = np.array(poly, np.int32)
            sig = ctrl["signal_states"].get(direction, "RED")
            color = (0, 255, 0) if sig == "GREEN" else ((0, 215, 255) if sig == "YELLOW" else (0, 0, 255))
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(out, [pts], True, color, 2)
            mx = int(np.mean([p[0] for p in poly]))
            my = int(np.mean([p[1] for p in poly]))
            cv2.putText(out, f"{direction} APPROACH", (mx, my), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.addWeighted(overlay, 0.15, out, 0.85, 0, out)

        # 2. Draw Intersection Box
        ibox = self.lane_manager.get_pixel_box(self.lane_manager.intersection_box, w, h)
        cv2.rectangle(out, (ibox[0], ibox[1]), (ibox[2], ibox[3]), (255, 255, 0), 2)
        cv2.putText(out, "INTERSECTION ZONE", (ibox[0] + 5, ibox[1] + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)

        # 2b. Signal-gated Stop Lines (vehicles MUST stop behind these when RED)
        #     For each approach, the stop line is the ROI edge nearest the intersection.
        cx = (ibox[0] + ibox[2]) / 2.0
        cy = (ibox[1] + ibox[3]) / 2.0
        for direction in ["NORTH", "SOUTH", "EAST", "WEST"]:
            poly = self.lane_manager.get_pixel_polygon(self.lane_manager.rois[direction], w, h)
            if len(poly) < 3:
                continue
            best = None
            best_mid = None
            best_d = 1e18
            n = len(poly)
            for i in range(n):
                p1 = poly[i]
                p2 = poly[(i + 1) % n]
                mx2 = (p1[0] + p2[0]) / 2.0
                my2 = (p1[1] + p2[1]) / 2.0
                d = (mx2 - cx) ** 2 + (my2 - cy) ** 2
                if d < best_d:
                    best_d = d
                    best = (p1, p2)
                    best_mid = (int(mx2), int(my2))
            sig = ctrl["signal_states"].get(direction, "RED")
            color = (0, 255, 0) if sig == "GREEN" else ((0, 215, 255) if sig == "YELLOW" else (0, 0, 255))
            cv2.line(out, best[0], best[1], color, 8)
            tx, ty = best_mid
            dy = ty - cy
            label_y = ty + (22 if dy >= 0 else -6)
            if sig == "GREEN":
                cv2.putText(out, "GO", (tx + 6, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            elif sig == "YELLOW":
                cv2.putText(out, "CAUTION", (tx + 6, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 215, 255), 2)
            else:
                cv2.putText(out, "STOP HERE", (tx + 6, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # 3. Draw Tracked Vehicles
        for veh in tracked:
            bbox = veh.get("bbox", [])
            if len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                vid = veh.get("id")
                cls_name = veh.get("class")
                conf = veh.get("confidence", 0.0)
                v_wait = veh.get("waiting_time", 0.0)
                status = veh.get("status", "")
                stopped = veh.get("stopped", False)
                ran_red = veh.get("ran_red", False)

                if stopped:
                    blink = 1 if int(time.time() * 2) % 2 else 0
                    box_color = (0, 0, 255)
                    overlay = out.copy()
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), box_color, -1)
                    cv2.addWeighted(overlay, 0.45, out, 0.55, 0, out)
                    cv2.rectangle(out, (x1, y1), (x2, y2), box_color, 3 - blink)
                    direction = veh.get("direction", "?")
                    cx_c = (ibox[0] + ibox[2]) // 2
                    cy_c = (ibox[1] + ibox[3]) // 2
                    cv2.line(out, ((x1 + x2) // 2, (y1 + y2) // 2), (cx_c, cy_c), (0, 0, 255), 1)
                    label = f"#STOP {vid} {v_wait:.1f}s [{direction} RED]"
                    cv2.rectangle(out, (x1, max(0, y1 - 20)), (x1 + len(label) * 8 + 10, max(20, y1)), (0, 0, 255), -1)
                    cv2.putText(out, label, (x1 + 3, max(15, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
                elif ran_red:
                    box_color = (255, 0, 255)
                    cv2.rectangle(out, (x1, y1), (x2, y2), box_color, 2)
                    label = f"#RAN RED {vid} {cls_name}"
                    cv2.rectangle(out, (x1, max(0, y1 - 20)), (x1 + len(label) * 8 + 10, max(20, y1)), box_color, -1)
                    cv2.putText(out, label, (x1 + 3, max(15, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
                else:
                    box_color = (0, 255, 0) if status == "Crossing" else ((0, 165, 255) if status == "Waiting" else (255, 200, 0))
                    cv2.rectangle(out, (x1, y1), (x2, y2), box_color, 2)

                    direction = veh.get("direction", "?")
                    label = f"#{vid} {cls_name} {conf:.2f} [{direction}]"
                    if v_wait > 0.5:
                        label += f" ({v_wait:.1f}s)"

                    cv2.rectangle(out, (x1, max(0, y1 - 20)), (x1 + len(label) * 8 + 10, max(20, y1)), box_color, -1)
                    cv2.putText(out, label, (x1 + 3, max(15, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)

        # 4. Draw Header Status HUD
        curr_d = ctrl["current_direction"]
        pstate = ctrl["phase_state"]
        trem = ctrl["timer_remaining"]
        next_d = ctrl["next_direction"]

        hud_text = f"ACTIVE: {curr_d} [{pstate}] {trem:.1f}s | NEXT: {next_d} (Pri: {ctrl['next_priority_score']:.1f}) | FPS: {self.fps_actual}"
        cv2.rectangle(out, (10, 10), (w - 10, 45), (15, 15, 15), -1)
        hud_color = (0, 255, 0) if pstate == "GREEN" else ((0, 215, 255) if pstate == "YELLOW" else (0, 0, 255))
        cv2.rectangle(out, (10, 10), (w - 10, 45), hud_color, 2)
        cv2.putText(out, hud_text, (20, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # 5. Per-Approach Live Stats Panel (real backend values only)
        order = ["NORTH", "EAST", "SOUTH", "WEST"]
        panel_x = 10
        panel_w = 208
        row_h = 44
        for row, direction in enumerate(order):
            sig = ctrl["signal_states"].get(direction, "RED")
            count = counts.get(direction, 0)
            waiting = wait_stats.get(direction, {}).get("wait_count", 0)
            avg = wait_stats.get(direction, {}).get("avg_wait", 0.0)
            pri = ctrl["priorities"].get(direction, 0.0)
            y0 = 56 + row_h * row
            pcolor = (0, 255, 0) if sig == "GREEN" else ((0, 215, 255) if sig == "YELLOW" else (0, 0, 255))
            cv2.rectangle(out, (panel_x, y0), (panel_x + panel_w, y0 + row_h - 3), (20, 20, 20), -1)
            cv2.rectangle(out, (panel_x, y0), (panel_x + 6, y0 + row_h - 3), pcolor, -1)
            cv2.putText(out, f"{direction}  {sig}", (panel_x + 12, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.putText(out, f"V:{count}  W:{waiting}  AVG:{avg:.1f}s", (panel_x + 12, y0 + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1)
            pri_color = (0, 255, 0) if sig == "GREEN" else (255, 255, 255)
            cv2.putText(out, f"PRI:{pri:.1f}", (panel_x + panel_w - 86, y0 + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.42, pri_color, 1)

        return out

    def get_latest_frame_bytes(self) -> Optional[bytes]:
        with self.lock:
            if self.latest_frame is None:
                return None
            ret, jpeg = cv2.imencode(".jpg", self.latest_frame)
            if ret:
                return jpeg.tobytes()
        return None

    def get_latest_state(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.latest_state)
