import random
import time
import math
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
from backend.traffic.lane_manager import LaneManager
from backend.traffic.vehicle_counter import VehicleCounter
from backend.traffic.density import DensityCalculator
from backend.traffic.waiting_time import WaitingTimeTracker
from backend.traffic.priority import PriorityCalculator
from backend.traffic.signal_controller import SignalController
from backend.config import TrafficSystemConfig


class SimVehicle:
    def __init__(self, vid: int, direction: str, vtype: str = "car"):
        self.id = vid
        self.direction = direction  # 'NORTH', 'SOUTH', 'EAST', 'WEST'
        self.vtype = vtype

        # Vehicle size
        if vtype == "bus":
            self.length = 36
            self.width = 18
            self.color = (50, 160, 220)  # Orange/Gold
        elif vtype == "van":
            self.length = 26
            self.width = 15
            self.color = (180, 120, 50)  # Blueish
        else:
            self.length = 20
            self.width = 13
            # Random car colors: white, red, blue, silver, black
            self.color = random.choice([
                (220, 220, 220), (50, 50, 210), (200, 100, 50), (140, 140, 140), (40, 40, 40)
            ])

        # Normalized coordinates [0..1]
        self.x = 0.0
        self.y = 0.0
        self.speed = 0.0
        self.target_speed = random.uniform(0.12, 0.18)  # normalized units/sec

        self.in_intersection = False
        self.has_crossed = False
        self.counted_as_passed = False
        self.waiting_time = 0.0

        self._init_position()

    def _init_position(self):
        # Two lanes per approach, offset from the center line so opposing
        # directions never share a lane (prevents head-on overlap).
        lane_off = random.choice([0.0, 0.04])
        if self.direction == "NORTH":
            self.x = 0.44 + lane_off
            self.y = -0.05
        elif self.direction == "SOUTH":
            self.x = 0.52 + lane_off
            self.y = 1.05
        elif self.direction == "WEST":
            self.x = -0.05
            self.y = 0.44 + lane_off
        elif self.direction == "EAST":
            self.x = 1.05
            self.y = 0.52 + lane_off


class IntersectionSimulation:
    """
    Realistic 4-Way Traffic Intersection Simulator using the EXACT same traffic intelligence
    (VehicleCounter, DensityCalculator, WaitingTimeTracker, PriorityCalculator, SignalController).
    """
    def __init__(self, config: TrafficSystemConfig):
        self.config = config
        self.vehicles: List[SimVehicle] = []
        self.next_vehicle_id = 100

        # Core traffic modules
        self.lane_manager = LaneManager(config.rois, config.intersection_box)
        self.counter = VehicleCounter()
        self.density_calc = DensityCalculator(
            low_max=config.density_low_max,
            med_max=config.density_medium_max,
            max_capacity=20
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

        # Spawn timing
        self.spawn_intervals = {
            "NORTH": random.uniform(1.2, 3.0),
            "SOUTH": random.uniform(1.5, 3.5),
            "EAST": random.uniform(1.0, 2.5),
            "WEST": random.uniform(2.0, 4.0)
        }
        self.spawn_timers = {d: 0.0 for d in self.spawn_intervals}

        self.last_update_time = time.time()
        self.is_running = True

        # Stop lines (normalized positions)
        self.stop_lines = {
            "NORTH": 0.38,  # y coordinate
            "SOUTH": 0.62,  # y coordinate
            "WEST":  0.38,  # x coordinate
            "EAST":  0.62   # x coordinate
        }

    def spawn_vehicle(self, direction: str):
        vtype = random.choices(["car", "van", "bus"], weights=[0.75, 0.15, 0.10])[0]
        veh = SimVehicle(self.next_vehicle_id, direction, vtype)
        self.next_vehicle_id += 1
        self.vehicles.append(veh)

    def _spawn_slot_free(self, direction: str) -> bool:
        for o in self.vehicles:
            if o.direction != direction:
                continue
            if direction in ["NORTH", "SOUTH"] and abs(o.x - 0.50) < 0.06:
                if direction == "NORTH" and o.y < 0.06:
                    return False
                if direction == "SOUTH" and o.y > 0.94:
                    return False
            if direction in ["WEST", "EAST"] and abs(o.y - 0.50) < 0.06:
                if direction == "WEST" and o.x < 0.06:
                    return False
                if direction == "EAST" and o.x > 0.94:
                    return False
        return True

    def step(self, dt: float) -> Tuple[Dict[str, Any], np.ndarray]:
        """
        Runs one simulation step of duration dt seconds.
        Returns: (state_dict, annotated_opencv_frame)
        """
        # 1. Spawning
        for d in ["NORTH", "SOUTH", "EAST", "WEST"]:
            self.spawn_timers[d] += dt
            if self.spawn_timers[d] >= self.spawn_intervals[d]:
                self.spawn_timers[d] = 0.0
                self.spawn_intervals[d] = random.uniform(1.5, 4.5)
                # Cap number of active vehicles per lane to prevent infinite overflow
                lane_count = sum(1 for v in self.vehicles if v.direction == d and not v.has_crossed)
                if lane_count < 18 and self._spawn_slot_free(d):
                    self.spawn_vehicle(d)

        # 2. Vehicle movement and queuing physics
        signal_states = self.signal_controller.get_signal_states()
        self._update_vehicle_physics(dt, signal_states)

        # 3. Format tracked vehicles list for traffic intelligence
        tracked_list = []
        w_px, h_px = 800, 800
        for v in self.vehicles:
            cx_px = int(v.x * w_px)
            cy_px = int(v.y * h_px)
            tracked_list.append({
                "id": v.id,
                "class": v.vtype,
                "direction": v.direction,
                "speed": v.speed * w_px,  # convert to px/sec
                "in_intersection": v.in_intersection,
                "has_crossed": v.has_crossed,
                "counted_as_passed": v.counted_as_passed,
                "center_x": cx_px,
                "center_y": cy_px,
                "waiting_time": v.waiting_time,
                "status": "Crossing" if v.in_intersection else ("Passed" if v.has_crossed else ("Waiting" if v.waiting_time > 0.5 else "Approaching"))
            })

        # 4. Vehicle counting & density
        active_counts = self.counter.update_from_tracked_vehicles(tracked_list)
        density_levels = self.density_calc.update(active_counts)

        # 5. Waiting time calculation
        waiting_stats = self.wait_tracker.update(tracked_list, signal_states, dt)

        # Sync waiting time back to vehicle objects
        for v, t in zip(self.vehicles, tracked_list):
            v.waiting_time = t.get("waiting_time", 0.0)

        # 6. Signal controller step (State machine transition)
        ctrl_state = self.signal_controller.step(dt, active_counts, waiting_stats)

        # 7. Render visualization frame
        frame = self._render_frame(w_px, h_px, ctrl_state, active_counts, density_levels, waiting_stats)

        # Cleanup vehicles that have left the screen
        self.vehicles = [
            v for v in self.vehicles
            if -0.2 <= v.x <= 1.2 and -0.2 <= v.y <= 1.2
        ]

        # Prepare unified response payload
        directions_summary = {}
        for d in ["NORTH", "SOUTH", "EAST", "WEST"]:
            d_level, d_pct = density_levels.get(d, ("LOW", 0.0))
            w_info = waiting_stats.get(d, {})
            directions_summary[d] = {
                "direction": d,
                "count": active_counts.get(d, 0),
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
            "mode": "simulation",
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
            "fps": round(1.0 / max(dt, 0.001), 1),
            "adaptive_mode": self.signal_controller.adaptive_mode,
            "directions": directions_summary,
            "tracked_vehicles": tracked_list,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        return state, frame

    def _update_vehicle_physics(self, dt: float, signal_states: Dict[str, str]):
        """Car-following and signal stopping physics"""
        for v in self.vehicles:
            sig = signal_states.get(v.direction, "RED")
            cross_clear = not any(o.in_intersection for o in self.vehicles if o.direction != v.direction)
            can_pass = ((sig == "GREEN" and cross_clear) or v.in_intersection or v.has_crossed)

            # Determine distance to stop line or car ahead
            desired_speed = v.target_speed

            if v.direction == "NORTH":
                # Moving downwards (y increases)
                if not v.in_intersection and not v.has_crossed:
                    dist_to_stop = self.stop_lines["NORTH"] - v.y
                    if not can_pass and dist_to_stop > 0 and dist_to_stop < 0.25:
                        desired_speed = min(desired_speed, max(0.0, dist_to_stop * 1.5))
                        if dist_to_stop < 0.03:
                            desired_speed = 0.0

                # Distance to vehicle ahead (queue lane discipline, all states)
                ahead = [o for o in self.vehicles if o.direction == "NORTH" and o.y > v.y and abs(o.x - v.x) < 0.05]
                if ahead:
                    closest = min(ahead, key=lambda o: o.y - v.y)
                    gap = (closest.y - v.y)
                    if gap < 0.08:
                        desired_speed = min(desired_speed, closest.speed * 0.8)
                    if gap < 0.045:
                        desired_speed = 0.0

                v.speed = desired_speed
                v.y += v.speed * dt
                if 0.38 <= v.y <= 0.62:
                    v.in_intersection = True
                elif v.y > 0.62:
                    v.in_intersection = False
                    v.has_crossed = True

            elif v.direction == "SOUTH":
                # Moving upwards (y decreases)
                if not v.in_intersection and not v.has_crossed:
                    dist_to_stop = v.y - self.stop_lines["SOUTH"]
                    if not can_pass and dist_to_stop > 0 and dist_to_stop < 0.25:
                        desired_speed = min(desired_speed, max(0.0, dist_to_stop * 1.5))
                        if dist_to_stop < 0.03:
                            desired_speed = 0.0

                ahead = [o for o in self.vehicles if o.direction == "SOUTH" and o.y < v.y and abs(o.x - v.x) < 0.05]
                if ahead:
                    closest = min(ahead, key=lambda o: v.y - o.y)
                    gap = (v.y - closest.y)
                    if gap < 0.08:
                        desired_speed = min(desired_speed, closest.speed * 0.8)
                    if gap < 0.045:
                        desired_speed = 0.0

                v.speed = desired_speed
                v.y -= v.speed * dt
                if 0.38 <= v.y <= 0.62:
                    v.in_intersection = True
                elif v.y < 0.38:
                    v.in_intersection = False
                    v.has_crossed = True

            elif v.direction == "WEST":
                # Moving right (x increases)
                if not v.in_intersection and not v.has_crossed:
                    dist_to_stop = self.stop_lines["WEST"] - v.x
                    if not can_pass and dist_to_stop > 0 and dist_to_stop < 0.25:
                        desired_speed = min(desired_speed, max(0.0, dist_to_stop * 1.5))
                        if dist_to_stop < 0.03:
                            desired_speed = 0.0

                ahead = [o for o in self.vehicles if o.direction == "WEST" and o.x > v.x and abs(o.y - v.y) < 0.05]
                if ahead:
                    closest = min(ahead, key=lambda o: o.x - v.x)
                    gap = (closest.x - v.x)
                    if gap < 0.08:
                        desired_speed = min(desired_speed, closest.speed * 0.8)
                    if gap < 0.045:
                        desired_speed = 0.0

                v.speed = desired_speed
                v.x += v.speed * dt
                if 0.38 <= v.x <= 0.62:
                    v.in_intersection = True
                elif v.x > 0.62:
                    v.in_intersection = False
                    v.has_crossed = True

            elif v.direction == "EAST":
                # Moving left (x decreases)
                if not v.in_intersection and not v.has_crossed:
                    dist_to_stop = v.x - self.stop_lines["EAST"]
                    if not can_pass and dist_to_stop > 0 and dist_to_stop < 0.25:
                        desired_speed = min(desired_speed, max(0.0, dist_to_stop * 1.5))
                        if dist_to_stop < 0.03:
                            desired_speed = 0.0

                ahead = [o for o in self.vehicles if o.direction == "EAST" and o.x < v.x and abs(o.y - v.y) < 0.05]
                if ahead:
                    closest = min(ahead, key=lambda o: v.x - o.x)
                    gap = (v.x - closest.x)
                    if gap < 0.08:
                        desired_speed = min(desired_speed, closest.speed * 0.8)
                    if gap < 0.045:
                        desired_speed = 0.0

                v.speed = desired_speed
                v.x -= v.speed * dt
                if 0.38 <= v.x <= 0.62:
                    v.in_intersection = True
                elif v.x < 0.38:
                    v.in_intersection = False
                    v.has_crossed = True

    def _render_frame(
        self,
        w: int,
        h: int,
        ctrl_state: Dict[str, Any],
        counts: Dict[str, int],
        densities: Dict[str, Tuple[str, float]],
        wait_stats: Dict[str, Dict[str, float]]
    ) -> np.ndarray:
        """Draws realistic four-way intersection with roads, signals, and moving vehicles"""
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        # Grass background
        frame[:] = (34, 85, 34)

        # Road dimensions
        rw = int(w * 0.24)  # road width
        cx, cy = w // 2, h // 2

        # Draw Asphalt Roads (Dark Grey)
        cv2.rectangle(frame, (cx - rw // 2, 0), (cx + rw // 2, h), (45, 45, 45), -1)
        cv2.rectangle(frame, (0, cy - rw // 2), (w, cy + rw // 2), (45, 45, 45), -1)

        # Yellow center lines
        cv2.line(frame, (cx, 0), (cx, cy - rw // 2), (0, 215, 255), 2)
        cv2.line(frame, (cx, cy + rw // 2), (cx, h), (0, 215, 255), 2)
        cv2.line(frame, (0, cy), (cx - rw // 2, cy), (0, 215, 255), 2)
        cv2.line(frame, (cx + rw // 2, cy), (w, cy), (0, 215, 255), 2)

        # Stop lines (Solid White)
        cv2.line(frame, (cx, int(h * 0.38)), (cx + rw // 2, int(h * 0.38)), (255, 255, 255), 4)  # North
        cv2.line(frame, (cx - rw // 2, int(h * 0.62)), (cx, int(h * 0.62)), (255, 255, 255), 4)  # South
        cv2.line(frame, (int(w * 0.38), cy - rw // 2), (int(w * 0.38), cy), (255, 255, 255), 4)  # West
        cv2.line(frame, (int(w * 0.62), cy), (int(w * 0.62), cy + rw // 2), (255, 255, 255), 4)  # East

        # Intersection Box dotted boundary
        ix1, iy1 = int(w * 0.38), int(h * 0.38)
        ix2, iy2 = int(w * 0.62), int(h * 0.62)
        cv2.rectangle(frame, (ix1, iy1), (ix2, iy2), (80, 80, 80), 1)

        # Draw Traffic Signals at each corner of intersection
        signals = ctrl_state["signal_states"]
        signal_coords = {
            "NORTH": (cx + rw // 2 + 15, int(h * 0.36)),
            "SOUTH": (cx - rw // 2 - 45, int(h * 0.64)),
            "WEST":  (int(w * 0.36), cy - rw // 2 - 45),
            "EAST":  (int(w * 0.64), cy + rw // 2 + 15),
        }

        for d, (sx, sy) in signal_coords.items():
            state = signals.get(d, "RED")
            # Traffic light housing
            cv2.rectangle(frame, (sx, sy), (sx + 30, sy + 30), (20, 20, 20), -1)
            cv2.rectangle(frame, (sx, sy), (sx + 30, sy + 30), (120, 120, 120), 1)

            if state == "GREEN":
                light_color = (0, 255, 0)
            elif state == "YELLOW":
                light_color = (0, 220, 255)
            else:
                light_color = (0, 0, 255)

            cv2.circle(frame, (sx + 15, sy + 15), 10, light_color, -1)

        # Draw Vehicles
        for v in self.vehicles:
            vx, vy = int(v.x * w), int(v.y * h)
            # Oriented bounding box
            if v.direction in ["NORTH", "SOUTH"]:
                vw, vh = v.width, v.length
            else:
                vw, vh = v.length, v.width

            bx1, by1 = vx - vw // 2, vy - vh // 2
            bx2, by2 = vx + vw // 2, vy + vh // 2

            # Vehicle body
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), v.color, -1)
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (255, 255, 255), 1)

            # Headlights / Taillights
            if v.direction == "NORTH":
                cv2.circle(frame, (bx1 + 3, by2 - 2), 2, (0, 255, 255), -1)
                cv2.circle(frame, (bx2 - 3, by2 - 2), 2, (0, 255, 255), -1)
            elif v.direction == "SOUTH":
                cv2.circle(frame, (bx1 + 3, by1 + 2), 2, (0, 255, 255), -1)
                cv2.circle(frame, (bx2 - 3, by1 + 2), 2, (0, 255, 255), -1)
            elif v.direction == "WEST":
                cv2.circle(frame, (bx2 - 2, by1 + 3), 2, (0, 255, 255), -1)
                cv2.circle(frame, (bx2 - 2, by2 - 3), 2, (0, 255, 255), -1)
            elif v.direction == "EAST":
                cv2.circle(frame, (bx1 + 2, by1 + 3), 2, (0, 255, 255), -1)
                cv2.circle(frame, (bx1 + 2, by2 - 3), 2, (0, 255, 255), -1)

            # Label (ID)
            cv2.putText(frame, f"#{v.id}", (bx1 - 5, by1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

        # Direction HUD badges on four approaches
        hud_pos = {
            "NORTH": (cx + rw // 2 + 55, 80),
            "SOUTH": (20, h - 90),
            "EAST":  (w - 210, cy + rw // 2 + 55),
            "WEST":  (20, 80)
        }

        for d, (hx, hy) in hud_pos.items():
            cnt = counts.get(d, 0)
            lvl, pct = densities.get(d, ("LOW", 0.0))
            w_stat = wait_stats.get(d, {})
            avg_w = w_stat.get("avg_wait", 0.0)
            sig = signals.get(d, "RED")
            pri = ctrl_state["priorities"].get(d, 0.0)

            # Card background
            card_color = (0, 60, 0) if sig == "GREEN" else ((0, 60, 60) if sig == "YELLOW" else (20, 20, 20))
            cv2.rectangle(frame, (hx, hy), (hx + 190, hy + 90), card_color, -1)
            cv2.rectangle(frame, (hx, hy), (hx + 190, hy + 90), (0, 255, 0) if sig == "GREEN" else (100, 100, 100), 2)

            sig_badge = f"{d} [{sig}]"
            cv2.putText(frame, sig_badge, (hx + 8, hy + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0) if sig == "GREEN" else (0, 0, 255), 2)
            cv2.putText(frame, f"Vehicles: {cnt} | Pri: {pri:.1f}", (hx + 8, hy + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (230, 230, 230), 1)
            cv2.putText(frame, f"Density: {lvl} ({pct:.0f}%)", (hx + 8, hy + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)
            cv2.putText(frame, f"Avg Wait: {avg_w:.1f}s", (hx + 8, hy + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 180, 255), 1)

        # Central active green timer banner
        curr_dir = ctrl_state["current_direction"]
        time_rem = ctrl_state["timer_remaining"]
        pstate = ctrl_state["phase_state"]
        banner_text = f"ACTIVE: {curr_dir} ({pstate}) - {time_rem:.1f}s | NEXT: {ctrl_state['next_direction']}"
        cv2.rectangle(frame, (w // 2 - 250, 15), (w // 2 + 250, 48), (10, 10, 10), -1)
        cv2.rectangle(frame, (w // 2 - 250, 15), (w // 2 + 250, 48), (0, 255, 0) if pstate == "GREEN" else (0, 215, 255), 2)
        cv2.putText(frame, banner_text, (w // 2 - 240, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1)

        return frame
