import asyncio
import os
import threading
import time
from typing import Dict, Any, Optional, Tuple

import cv2
import numpy as np

from backend.config import TrafficSystemConfig, load_config, save_config, VIDEOS_INPUT_DIR
from backend.database.database import (
    start_session,
    end_session,
    record_traffic_metric,
    record_phase_switch,
    log_event,
)
from backend.services.simulation import IntersectionSimulation
from backend.services.video_processor import VideoProcessorService
from backend.websocket.traffic_socket import manager


class TrafficEngine:
    """
    Central engine that runs either the IntersectionSimulation or the
    VideoProcessorService in the background, keeps the latest traffic state
    and annotated frame, records analytics metrics, and broadcasts live
    state updates to all connected WebSocket clients.
    """

    def __init__(self):
        self.config: TrafficSystemConfig = load_config()
        self.simulation: Optional[IntersectionSimulation] = None
        self.video_processor: Optional[VideoProcessorService] = None

        self.mode: str = self.config.active_source or "simulation"
        self.is_running: bool = False
        self.is_paused: bool = False

        # Latest state + frame (updated by the background loop)
        self._lock = threading.Lock()
        self._last_state: Dict[str, Any] = {}
        self._last_frame: Optional[np.ndarray] = None
        self._frame_seq: int = 0
        self._error: Optional[str] = None

        # Async task handle + loop reference (captured at startup)
        self._task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._generation: int = 0

        # Session / analytics accounting
        self.session_id: Optional[int] = None
        self._total_vehicles: int = 0
        self._total_cycles: int = 0
        self._waiting_samples: list = []
        self._max_wait: float = 0.0
        self._green_samples: list = []
        self._last_metric_save: float = time.time()

    # ------------------------------------------------------------------
    # Public API (used by routes)
    # ------------------------------------------------------------------
    def get_latest_state(self) -> Dict[str, Any]:
        with self._lock:
            if self._last_state:
                return dict(self._last_state)
        return {
            "mode": self.mode,
            "active_direction": "NORTH",
            "active_signal_state": "GREEN",
            "total_active_vehicles": 0,
            "total_waiting_vehicles": 0,
            "total_passed_vehicles": 0,
            "system_avg_waiting_time": 0.0,
            "system_max_waiting_time": 0.0,
            "fps": 0.0,
            "directions": {
                d: {"direction": d, "count": 0, "waiting_count": 0, "signal_state": "RED", "priority_score": 0.0}
                for d in ["NORTH", "SOUTH", "EAST", "WEST"]
            },
            "tracked_vehicles": [],
            "error": self._error,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_latest_frame_jpeg(self) -> Tuple[int, Optional[bytes]]:
        with self._lock:
            if self._last_frame is None:
                return self._frame_seq, None
            ret, jpeg = cv2.imencode(".jpg", self._last_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            if not ret:
                return self._frame_seq, None
            return self._frame_seq, jpeg.tobytes()

    def get_status(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "session_id": self.session_id,
            "selected_video": self.config.selected_video,
            "error": self._error,
            "frames_ready": self._frame_seq > 0,
        }

    # ------------------------------------------------------------------
    # Lifecycle (async context expected)
    # ------------------------------------------------------------------
    def start(self):
        """Start the engine. Safe to call from the event loop thread or a worker thread."""
        if self.is_running:
            return
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        self.is_running = True
        self.is_paused = False
        self._error = None
        if self.session_id is None:
            source = self.config.selected_video if self.mode == "video" else "simulation-engine"
            self.session_id = start_session(self.mode, source or self.mode)
        in_loop_thread = True
        try:
            in_loop_thread = self._loop is not None and asyncio.get_running_loop() is self._loop
        except RuntimeError:
            in_loop_thread = False
        self._generation += 1
        gen = self._generation
        if self._loop is not None and self._loop.is_running() and not in_loop_thread:
            self._task = asyncio.run_coroutine_threadsafe(self._run_loop(gen), self._loop)
        else:
            self._task = asyncio.create_task(self._run_loop(gen))

    def stop(self):
        self.is_running = False
        if self.video_processor:
            self.video_processor.stop()
            self.video_processor = None
        if self._task:
            try:
                self._task.cancel()
            except Exception:
                pass
        self._finish_session()

    def toggle_pause(self) -> bool:
        if self.mode == "video" and self.video_processor:
            self.video_processor.pause()
            self.is_paused = self.video_processor.is_paused
        else:
            self.is_paused = not self.is_paused
        log_event(f"Traffic engine {'paused' if self.is_paused else 'resumed'}", "INFO", "CONTROL")
        return self.is_paused

    def restart(self):
        was_running = self.is_running
        self.stop()
        self._reset_summary()
        self.session_id = None
        if was_running:
            self.start()

    def switch_mode(self, mode: str, video_name: Optional[str] = None):
        """Switch between 'simulation' and 'video' modes safely."""
        mode = "video" if mode == "video" else "simulation"

        self.stop()
        self._reset_summary()
        self.session_id = None

        self.mode = mode
        self.config.active_source = mode
        if mode == "video" and video_name:
            self.config.selected_video = str(VIDEOS_INPUT_DIR / video_name)
        save_config(self.config)

        log_event(f"Switched mode to {mode}{' (' + video_name + ')' if video_name else ''}", "INFO", "CONTROL")
        self.start()

    def manual_signal(self, direction: str, duration: float = 15.0):
        direction = direction.upper()
        if direction not in ["NORTH", "SOUTH", "EAST", "WEST"]:
            return {"status": "error", "detail": "Invalid direction"}
        controller = self._active_controller()
        if controller:
            controller.manual_switch(direction, duration)
            log_event(f"Manual signal switch requested to {direction} ({duration}s)", "INFO", "SIGNAL")
            return {"status": "success", "direction": direction, "duration": duration}
        return {"status": "error", "detail": "No active traffic controller"}

    def set_adaptive(self, adaptive: bool):
        self.config.adaptive_mode = bool(adaptive)
        save_config(self.config)
        controller = self._active_controller()
        if controller:
            controller.adaptive_mode = bool(adaptive)
        log_event(f"Adaptive mode {'enabled' if adaptive else 'disabled'}", "INFO", "CONFIG")
        return {"status": "success", "adaptive_mode": bool(adaptive)}

    def reload_config(self):
        """Re-apply the saved config to running components after a config update."""
        self.config = load_config()
        if self.simulation:
            self.simulation.config = self.config
            self.simulation.lane_manager.update_rois(self.config.rois, self.config.intersection_box)
        if self.video_processor:
            self.video_processor.config = self.config
            self.video_processor.lane_manager.update_rois(self.config.rois, self.config.intersection_box)
        controller = self._active_controller()
        if controller:
            controller.adaptive_mode = self.config.adaptive_mode
            if hasattr(controller, "priority_calc"):
                controller.priority_calc.update_params(
                    self.config.density_weight,
                    self.config.waiting_weight,
                    self.config.starvation_threshold_seconds,
                    self.config.min_green_time,
                    self.config.max_green_time,
                    self.config.headway_seconds,
                    self.config.start_window_seconds,
                )
                controller.yellow_duration = self.config.yellow_time
                controller.all_red_duration = self.config.all_red_time

    def start_video_processing(self, video_name: str):
        self.stop()
        self._reset_summary()
        self.session_id = None
        self.mode = "video"
        video_path = VIDEOS_INPUT_DIR / video_name
        if not video_path.exists():
            self._fallback_to_simulation(f"Video not found: {video_name}")
            self.start()
            return {"status": "error", "detail": f"Video not found: {video_name}"}
        self.config.selected_video = str(video_path)
        self.config.active_source = "video"
        save_config(self.config)
        self.start()
        return {"status": "success", "mode": "video", "video": video_name}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _active_controller(self):
        if self.is_running:
            if self.mode == "simulation" and self.simulation:
                return self.simulation.signal_controller
            if self.mode == "video" and self.video_processor:
                return self.video_processor.signal_controller
        return None

    def _reset_summary(self):
        self._total_vehicles = 0
        self._total_cycles = 0
        self._waiting_samples = []
        self._max_wait = 0.0
        self._green_samples = []
        self._last_metric_save = time.time()

    def _finish_session(self):
        if self.session_id is None:
            return
        sid = self.session_id
        self.session_id = None
        avg_wait = sum(self._waiting_samples) / len(self._waiting_samples) if self._waiting_samples else 0.0
        max_wait = self._max_wait
        avg_green = sum(self._green_samples) / len(self._green_samples) if self._green_samples else 0.0
        end_session(sid, {
            "total_vehicles": self._total_vehicles,
            "total_cycles": self._total_cycles,
            "avg_waiting_time": avg_wait,
            "max_waiting_time": max_wait,
            "avg_green_duration": avg_green,
        })

    def _record_metric(self, state: Dict[str, Any]):
        if self.session_id is None:
            return
        now = time.time()
        if now - self._last_metric_save < 3.0:
            return
        self._last_metric_save = now
        dirs = state.get("directions", {})
        record_traffic_metric(self.session_id, {
            "north_count": dirs.get("NORTH", {}).get("count", 0),
            "south_count": dirs.get("SOUTH", {}).get("count", 0),
            "east_count": dirs.get("EAST", {}).get("count", 0),
            "west_count": dirs.get("WEST", {}).get("count", 0),
            "north_density": dirs.get("NORTH", {}).get("density_level", "LOW"),
            "south_density": dirs.get("SOUTH", {}).get("density_level", "LOW"),
            "east_density": dirs.get("EAST", {}).get("density_level", "LOW"),
            "west_density": dirs.get("WEST", {}).get("density_level", "LOW"),
            "north_wait": dirs.get("NORTH", {}).get("avg_waiting_time", 0.0),
            "south_wait": dirs.get("SOUTH", {}).get("avg_waiting_time", 0.0),
            "east_wait": dirs.get("EAST", {}).get("avg_waiting_time", 0.0),
            "west_wait": dirs.get("WEST", {}).get("avg_waiting_time", 0.0),
            "current_green": state.get("active_direction", "NORTH"),
            "green_duration": int(state.get("current_green_time_assigned", 15)),
            "priority_scores": {
                d: dirs.get(d, {}).get("priority_score", 0.0) for d in ["NORTH", "SOUTH", "EAST", "WEST"]
            },
        })

    async def _broadcast_state(self, state: Dict[str, Any]):
        try:
            await manager.broadcast({"type": "state", "data": state})
        except Exception:
            pass

    async def _run_loop(self, gen: int):
        try:
            if self.mode == "simulation":
                self.simulation = IntersectionSimulation(self.config)
                self.simulation.signal_controller.set_callback(self._on_phase_switch)
                await self._simulation_loop(gen)
            else:
                await self._video_loop(gen)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._error = str(exc)
            log_event(f"Traffic engine error: {exc}", "ERROR", "ENGINE")
        finally:
            if gen == self._generation:
                self.is_running = False

    def _fallback_to_simulation(self, reason: str):
        """Keep the live feed alive by falling back to simulation mode."""
        log_event(f"{reason} - falling back to simulation mode", "WARN", "ENGINE")
        self._error = reason
        self.mode = "simulation"
        self.config.active_source = "simulation"
        save_config(self.config)

    async def _simulation_loop(self, gen: int):
        target_dt = 1.0 / max(1, self.config.processing_fps)
        last = time.time()
        while self.is_running and gen == self._generation:
            if self.is_paused:
                await asyncio.sleep(0.1)
                last = time.time()
                continue

            now = time.time()
            dt = max(0.001, min(now - last, 0.25))
            last = now

            state, frame = self.simulation.step(dt)
            with self._lock:
                self._last_state = state
                self._last_frame = frame
                self._frame_seq += 1

            self._update_summary(state)
            self._record_metric(state)
            await self._broadcast_state(state)

            elapsed = time.time() - now
            await asyncio.sleep(max(0.001, target_dt - elapsed))

    async def _video_loop(self, gen: int):
        video_path = self.config.selected_video
        if not video_path or not (isinstance(video_path, str) and os.path.exists(video_path)):
            # fallback: pick the first video available
            candidates = [
                c for c in VIDEOS_INPUT_DIR.glob("*")
                if c.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}
            ]
            if candidates:
                video_path = str(candidates[0])
                self.config.selected_video = video_path
                save_config(self.config)

        if not video_path or not os.path.exists(video_path):
            self._fallback_to_simulation("No video available. Switch back to simulation or upload a video.")
            self.simulation = IntersectionSimulation(self.config)
            self.simulation.signal_controller.set_callback(self._on_phase_switch)
            await self._simulation_loop()
            return

        self.video_processor = VideoProcessorService(self.config)
        if not self.video_processor.start(video_path, self.session_id):
            self._error = f"Failed to open video: {video_path}"
            return

        while self.is_running and gen == self._generation:
            if self.is_paused:
                await asyncio.sleep(0.1)
                continue
            state = self.video_processor.get_latest_state()
            frame = self.video_processor.latest_frame
            if state and frame is not None:
                with self._lock:
                    self._last_state = state
                    self._last_frame = frame
                    self._frame_seq += 1
                self._update_summary(state)
                await self._broadcast_state(state)
            await asyncio.sleep(0.08)

    def _update_summary(self, state: Dict[str, Any]):
        """Track cumulative session stats from state snapshots."""
        passed = state.get("total_passed_vehicles") or 0
        self._total_vehicles = max(self._total_vehicles, passed)
        sys_avg_wait = state.get("system_avg_waiting_time") or 0.0
        if sys_avg_wait > 0:
            self._waiting_samples.append(sys_avg_wait)
            if len(self._waiting_samples) > 2000:
                self._waiting_samples = self._waiting_samples[-2000:]
        sys_max_wait = state.get("system_max_waiting_time") or 0.0
        if sys_max_wait > self._max_wait:
            self._max_wait = sys_max_wait

    def _on_phase_switch(self, direction, from_st, to_st, duration, count, priority):
        log_event(
            f"Signal {direction}: {from_st} -> {to_st} (Assigned: {duration:.1f}s, Vehicles: {count}, Pri: {priority:.1f})",
            "INFO", "SIGNAL"
        )
        if to_st == "GREEN":
            self._total_cycles += 1
            self._green_samples.append(duration)
            if len(self._green_samples) > 2000:
                self._green_samples = self._green_samples[-2000:]
        if self.session_id:
            record_phase_switch(self.session_id, {
                "phase_direction": direction,
                "from_state": from_st,
                "to_state": to_st,
                "duration_assigned": duration,
                "vehicle_count": count,
                "priority_score": priority,
            })


engine = TrafficEngine()