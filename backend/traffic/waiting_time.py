import time
from typing import Dict, List, Any, Tuple


class WaitingTimeTracker:
    """
    Tracks waiting time for active vehicles per direction.
    A vehicle is waiting if:
      - It is in an approach ROI (not intersection, not crossed)
      - Its current speed is <= speed_threshold (or stationary)
      - Its approach signal is RED (or YELLOW)
    """
    def __init__(self, speed_threshold: float = 3.5):
        self.speed_threshold = speed_threshold
        # vehicle_id -> waiting time accumulated (seconds)
        self.vehicle_wait_times: Dict[int, float] = {}
        # direction -> total waiting starvation timer (seconds since last green ended)
        self.direction_starvation_timer: Dict[str, float] = {
            "NORTH": 0.0,
            "SOUTH": 0.0,
            "EAST": 0.0,
            "WEST": 0.0
        }

    def update(
        self,
        tracked_vehicles: List[Dict[str, Any]],
        signal_states: Dict[str, str],
        dt: float
    ) -> Dict[str, Dict[str, float]]:
        """
        tracked_vehicles: list of dicts with:
           { 'id': int, 'direction': str, 'speed': float, 'in_intersection': bool, 'has_crossed': bool }
        signal_states: { 'NORTH': 'RED'|'YELLOW'|'GREEN', ... }
        dt: time delta in seconds since last frame
        """
        active_ids = set()

        # Update per-vehicle waiting times
        for veh in tracked_vehicles:
            vid = veh.get("id")
            if vid is None:
                continue
            active_ids.add(vid)

            direction = veh.get("direction")
            in_intersection = veh.get("in_intersection", False)
            has_crossed = veh.get("has_crossed", False)
            speed = veh.get("speed", 0.0)

            # Check if direction signal is RED or YELLOW
            sig = signal_states.get(direction, "RED")
            is_stopped_or_slow = speed <= self.speed_threshold

            # A vehicle only WRITES waiting time while it actually waits:
            # in its approach, not yet crossing, held by a non-GREEN light and stopped/slow.
            is_waiting = bool(
                direction and not in_intersection and not has_crossed
                and sig != "GREEN" and is_stopped_or_slow
            )
            if is_waiting:
                self.vehicle_wait_times[vid] = self.vehicle_wait_times.get(vid, 0.0) + dt
            elif sig == "GREEN":
                # Vehicle is released or moving
                # Reset or keep until exited
                self.vehicle_wait_times[vid] = max(0.0, self.vehicle_wait_times.get(vid, 0.0) - dt * 2)

            veh["is_waiting"] = is_waiting
            veh["waiting_time"] = round(self.vehicle_wait_times.get(vid, 0.0), 1)

        # Cleanup removed vehicles
        stale_ids = [vid for vid in self.vehicle_wait_times if vid not in active_ids]
        for vid in stale_ids:
            del self.vehicle_wait_times[vid]

        # Update starvation timers per direction
        for direction, sig in signal_states.items():
            if sig == "GREEN":
                self.direction_starvation_timer[direction] = 0.0
            else:
                self.direction_starvation_timer[direction] += dt

        # Calculate directional averages, waiting counts and maximums
        direction_stats = {}
        for direction in ["NORTH", "SOUTH", "EAST", "WEST"]:
            waiting_now = [
                v.get("waiting_time", 0.0)
                for v in tracked_vehicles
                if v.get("direction") == direction and v.get("is_waiting")
            ]
            wait_count = len(waiting_now)
            avg_wait = sum(waiting_now) / wait_count if waiting_now else 0.0
            max_wait = max(waiting_now) if waiting_now else 0.0
            total_wait = sum(waiting_now)

            direction_stats[direction] = {
                "wait_count": wait_count,
                "avg_wait": round(avg_wait, 1),
                "max_wait": round(max_wait, 1),
                "total_wait": round(total_wait, 1),
                "starvation_timer": round(self.direction_starvation_timer.get(direction, 0.0), 1)
            }

        return direction_stats
