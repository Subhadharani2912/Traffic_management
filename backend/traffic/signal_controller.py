from enum import Enum
from typing import Dict, Tuple, Optional, Any
from backend.traffic.priority import PriorityCalculator


class SignalPhaseState(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ALL_RED = "ALL_RED"


class SignalController:
    """
    Robust State Machine Controller ensuring intersection safety.
    Transitions: GREEN -> YELLOW -> ALL_RED (clearance) -> GREEN
    Never allows conflicting approaches to have GREEN simultaneously.
    """
    def __init__(
        self,
        priority_calc: PriorityCalculator,
        yellow_duration: float = 3.0,
        all_red_duration: float = 1.0,
        adaptive_mode: bool = True
    ):
        self.priority_calc = priority_calc
        self.yellow_duration = yellow_duration
        self.all_red_duration = all_red_duration
        self.adaptive_mode = adaptive_mode

        self.current_direction: str = "NORTH"
        self.phase_state: SignalPhaseState = SignalPhaseState.GREEN
        self.timer_remaining: float = 0.0
        self.current_green_duration: float = 0.0
        self.green_elapsed: float = 0.0
        self.green_total: float = 0.0

        self.next_direction: str = "SOUTH"
        self.next_green_duration: float = 15.0
        self.next_priority_score: float = 0.0

        # Safety: current display state for each direction
        self.signal_states: Dict[str, str] = {
            "NORTH": "GREEN",
            "SOUTH": "RED",
            "EAST": "RED",
            "WEST": "RED"
        }
        self.cycles_completed: int = 0
        self.phase_switch_callback = None

        # Dedicated Safe Emergency Preemption State (Phase 2)
        self.emergency_active: bool = False
        self.emergency_direction: Optional[str] = None
        self.emergency_type: Optional[str] = None  # 'ambulance', 'fire_truck', 'police'
        self.emergency_vehicle_id: Optional[int] = None
        self.emergency_confidence: float = 0.0
        self.emergency_preemption_duration: float = 15.0
        self.emergency_timer_remaining: float = 0.0
        self.emergency_status: str = "IDLE"  # 'IDLE', 'TRANSITIONING', 'PREEMPTED', 'CLEARED'

    def set_callback(self, cb):
        self.phase_switch_callback = cb

    def get_signal_states(self) -> Dict[str, str]:
        """Ensures safety guarantee: only 1 direction can ever be GREEN or YELLOW."""
        return dict(self.signal_states)

    def get_emergency_state(self) -> Dict[str, Any]:
        """Returns current system-level emergency preemption telemetry state."""
        return {
            "active": self.emergency_active,
            "type": self.emergency_type,
            "direction": self.emergency_direction,
            "vehicle_id": self.emergency_vehicle_id,
            "confidence": round(self.emergency_confidence, 2),
            "duration": self.emergency_preemption_duration,
            "timer_remaining": max(0.0, round(self.emergency_timer_remaining, 1)),
            "status": self.emergency_status
        }

    def get_state(self) -> Dict[str, Any]:
        """Returns the current signal controller state snapshot."""
        return {
            "current_direction": self.current_direction,
            "phase_state": self.phase_state.value,
            "timer_remaining": max(0.0, round(self.timer_remaining, 1)),
            "current_green_duration": self.current_green_duration,
            "next_direction": self.next_direction,
            "next_green_duration": self.next_green_duration,
            "next_priority_score": self.next_priority_score,
            "signal_states": dict(self.signal_states),
            "cycles_completed": self.cycles_completed,
            "emergency": self.get_emergency_state()
        }

    def preempt_emergency(
        self,
        direction: str,
        duration: float = 15.0,
        emergency_type: str = "ambulance",
        vehicle_id: Optional[int] = None,
        confidence: float = 1.0
    ) -> bool:
        """
        Triggers safe emergency vehicle preemption without ever causing an unsafe
        RED -> GREEN direct jump.
        Safe transition order:
          Current GREEN -> YELLOW (clearance) -> ALL_RED (safety buffer) -> Emergency Direction GREEN
        If the emergency direction already has GREEN, its green timer is safely held.
        """
        if isinstance(duration, str):
            # Caller passed emergency_type as 2nd positional argument
            emergency_type, duration = duration, 15.0 if not isinstance(emergency_type, (int, float)) else emergency_type

        if direction not in ["NORTH", "SOUTH", "EAST", "WEST"]:
            return False

        # If already preempted for this exact direction, maintain priority without restarting cycle
        if self.emergency_active and self.emergency_direction == direction:
            self.emergency_timer_remaining = max(self.emergency_timer_remaining, duration)
            self.emergency_preemption_duration = max(self.emergency_preemption_duration, duration)
            return True

        self.emergency_active = True
        self.emergency_direction = direction
        self.emergency_type = emergency_type
        self.emergency_vehicle_id = vehicle_id
        self.emergency_confidence = confidence
        self.emergency_preemption_duration = duration
        self.emergency_timer_remaining = duration

        # Case 1: Emergency approach is ALREADY GREEN -> hold green immediately
        if self.current_direction == direction and self.phase_state == SignalPhaseState.GREEN:
            self.current_green_duration = max(self.current_green_duration, duration)
            self.timer_remaining = max(self.timer_remaining, duration)
            self.green_elapsed = 0.0
            self.emergency_status = "PREEMPTED"
            return True

        # Case 2: Another lane is active or signal is in transition -> Stage emergency next
        self.emergency_status = "TRANSITIONING"
        self.next_direction = direction
        self.next_green_duration = duration

        # If current phase is GREEN on another approach, safely trigger YELLOW clearance first
        if self.phase_state == SignalPhaseState.GREEN:
            self.phase_state = SignalPhaseState.YELLOW
            self.timer_remaining = self.yellow_duration
            self.signal_states[self.current_direction] = "YELLOW"
            if self.phase_switch_callback:
                self.phase_switch_callback(
                    self.current_direction, "GREEN", "YELLOW", self.yellow_duration,
                    0, 999.0
                )

        return True

    def clear_emergency(self):
        """Clears active emergency preemption and safely allows normal adaptive control to resume."""
        self.emergency_active = False
        self.emergency_status = "CLEARED"
        self.emergency_direction = None
        self.emergency_timer_remaining = 0.0

    def manual_switch(self, target_direction: str, duration: float = 15.0):
        """Allows testing manual signal change while preserving safety state transitions."""
        if target_direction not in ["NORTH", "SOUTH", "EAST", "WEST"]:
            return
        self.next_direction = target_direction
        self.next_green_duration = duration
        # Force current phase to yellow if green
        if self.phase_state == SignalPhaseState.GREEN:
            self.phase_state = SignalPhaseState.YELLOW
            self.timer_remaining = self.yellow_duration
            self.signal_states[self.current_direction] = "YELLOW"

    def _dynamic_green_seconds(self, count: int, avg_wait: float) -> float:
        """
        How much green time the active direction needs THIS frame, from its
        live queue: start window + queued vehicles x headway, capped at
        max_green_time so a lane can never monopolize the junction.
        Empty lanes get a quick pass-through. Waiting time only raises the
        lane's priority (selection), not the green timer itself.
        """
        return self.priority_calc.compute_green_duration(count, avg_wait)

    def _decide_yield_or_extend(
        self,
        counts: Dict[str, int],
        waiting_stats: Dict[str, Dict[str, float]],
        priorities: Dict[str, float],
        raw_need: float
    ) -> str:
        """
        After the current dynamic green batch is served, decide whether to:
        - 'yield'  : hand over green to a more urgent direction
        - 'extend' : keep serving this direction (fresh dynamic batch)
        Yields only when no direction is starved, the active lane's need is
        satisfied, and another lane is strictly more urgent (or is waiting
        while the active lane is empty).
        """
        # Phase 2: Emergency preemption lock
        if self.emergency_active:
            if self.current_direction == self.emergency_direction:
                if self.emergency_timer_remaining > 0:
                    return "extend"
                else:
                    self.clear_emergency()
                    return "yield"
            else:
                return "yield"

        cur_score = priorities.get(self.current_direction, 0.0)
        others = {d: v for d, v in priorities.items() if d != self.current_direction}
        best_other = max(others.values()) if others else 0.0
        other_demand = max((counts.get(d, 0) for d in others), default=0)
        starved_other = max(
            (waiting_stats.get(d, {}).get("starvation_timer", 0.0) for d in others),
            default=0.0
        )
        total_demand = sum(counts.values()) + sum(
            w.get("avg_wait", 0.0) for w in waiting_stats.values()
        )

        if total_demand <= 0:
            # No demand anywhere -> cycle through lanes with short dynamic greens
            # so the signal never looks stuck on a single direction.
            return "yield"

        # Fairness: never let one lane monopolize green beyond max_green tenure
        max_tenure = float(self.priority_calc.max_green)
        if self.green_total >= max_tenure and other_demand > 0:
            return "yield"

        expired = self.green_elapsed >= raw_need
        if not expired:
            return "extend"

        others_more_urgent = best_other > cur_score
        current_lane_empty = counts.get(self.current_direction, 0) == 0

        if (
            (others_more_urgent or starved_other > self.priority_calc.starvation_threshold)
            or (current_lane_empty and other_demand > 0)
        ):
            return "yield"
        return "extend"

    def step(
        self,
        dt: float,
        counts: Dict[str, int],
        waiting_stats: Dict[str, Dict[str, float]]
    ) -> Dict[str, Any]:
        """
        Executes one time step dt. Green phase duration is recomputed every
        frame from live density + waiting time instead of a fixed countdown.
        The active direction keeps green while it still needs it; it yields
        only when its need is satisfied AND another direction is more urgent.
        During active emergency preemption, normal adaptive selection is suspended,
        conflicting lanes safely clear through YELLOW and ALL_RED, and the
        emergency lane receives priority GREEN.
        """
        self.timer_remaining = max(0.0, self.timer_remaining - dt)

        # Continuously update priorities for dashboard preview
        priorities = self.priority_calc.calculate_priorities(counts, waiting_stats, self.current_direction)
        if self.adaptive_mode and not self.emergency_active:
            next_dir, next_dur = self.priority_calc.select_next_phase(priorities, self.current_direction, counts, waiting_stats)
            self.next_direction = next_dir
            self.next_green_duration = next_dur
            self.next_priority_score = priorities.get(next_dir, 0.0)
        elif self.emergency_active:
            self.next_direction = self.emergency_direction
            self.next_green_duration = self.emergency_preemption_duration
            self.next_priority_score = 999.0

        # --- State Machine Transitions ---
        if self.phase_state == SignalPhaseState.GREEN:
            self.green_elapsed += dt
            self.green_total += dt

            # If emergency is active on this lane, count down emergency duration
            if self.emergency_active and self.current_direction == self.emergency_direction:
                self.emergency_status = "PREEMPTED"
                self.emergency_timer_remaining = max(0.0, self.emergency_timer_remaining - dt)
                self.timer_remaining = self.emergency_timer_remaining
                self.current_green_duration = self.emergency_preemption_duration

                if self.emergency_timer_remaining <= 0:
                    # Emergency pass finished, clear emergency preemption and yield
                    self.clear_emergency()
                    self.phase_state = SignalPhaseState.YELLOW
                    self.timer_remaining = self.yellow_duration
                    self.signal_states[self.current_direction] = "YELLOW"
                    if self.phase_switch_callback:
                        self.phase_switch_callback(
                            self.current_direction, "GREEN", "YELLOW", self.yellow_duration,
                            counts.get(self.current_direction, 0),
                            priorities.get(self.current_direction, 0.0)
                        )
            elif self.emergency_active and self.current_direction != self.emergency_direction:
                # Conflicting lane is currently green; safely yield immediately to yellow
                self.emergency_status = "TRANSITIONING"
                self.phase_state = SignalPhaseState.YELLOW
                self.timer_remaining = self.yellow_duration
                self.signal_states[self.current_direction] = "YELLOW"
                if self.phase_switch_callback:
                    self.phase_switch_callback(
                        self.current_direction, "GREEN", "YELLOW", self.yellow_duration,
                        counts.get(self.current_direction, 0),
                        999.0
                    )
            else:
                # Normal adaptive green calculation
                raw_need = self._dynamic_green_seconds(
                    counts.get(self.current_direction, 0),
                    waiting_stats.get(self.current_direction, {}).get("avg_wait", 0.0)
                )
                self.current_green_duration = raw_need
                self.timer_remaining = max(0.0, raw_need - self.green_elapsed)

                state = self._decide_yield_or_extend(counts, waiting_stats, priorities, raw_need)
                if state == "yield":
                    # GREEN -> YELLOW
                    self.phase_state = SignalPhaseState.YELLOW
                    self.timer_remaining = self.yellow_duration
                    self.signal_states[self.current_direction] = "YELLOW"

                    if self.phase_switch_callback:
                        self.phase_switch_callback(
                            self.current_direction, "GREEN", "YELLOW", self.yellow_duration,
                            counts.get(self.current_direction, 0),
                            priorities.get(self.current_direction, 0.0)
                        )
                elif self.green_elapsed >= raw_need:
                    # Served the dynamic batch; extend with a fresh dynamic batch
                    self.green_elapsed = 0.0
                    self.timer_remaining = raw_need

        elif self.phase_state == SignalPhaseState.YELLOW:
            if self.timer_remaining <= 0:
                # YELLOW -> ALL_RED
                self.phase_state = SignalPhaseState.ALL_RED
                self.timer_remaining = self.all_red_duration
                self.signal_states[self.current_direction] = "RED"

                if self.phase_switch_callback:
                    self.phase_switch_callback(
                        self.current_direction, "YELLOW", "RED", self.all_red_duration,
                        counts.get(self.current_direction, 0),
                        priorities.get(self.current_direction, 0.0)
                    )

        elif self.phase_state == SignalPhaseState.ALL_RED:
            if self.timer_remaining <= 0:
                # ALL_RED -> GREEN for next direction
                self.current_direction = self.next_direction
                self.phase_state = SignalPhaseState.GREEN
                self.green_elapsed = 0.0
                self.green_total = 0.0

                if self.emergency_active and self.current_direction == self.emergency_direction:
                    self.emergency_status = "PREEMPTED"
                    self.current_green_duration = self.emergency_preemption_duration
                    self.timer_remaining = self.emergency_timer_remaining
                else:
                    self.timer_remaining = 0.0
                    self.current_green_duration = 0.0

                # Safety: clear all other lights to RED, set only active to GREEN
                for d in ["NORTH", "SOUTH", "EAST", "WEST"]:
                    self.signal_states[d] = "GREEN" if d == self.current_direction else "RED"

                self.cycles_completed += 1

                if self.phase_switch_callback:
                    self.phase_switch_callback(
                        self.current_direction, "RED", "GREEN", self.current_green_duration,
                        counts.get(self.current_direction, 0),
                        self.next_priority_score
                    )

        return {
            "current_direction": self.current_direction,
            "phase_state": self.phase_state.value,
            "timer_remaining": max(0.0, round(self.timer_remaining, 1)),
            "current_green_duration": self.current_green_duration,
            "next_direction": self.next_direction,
            "next_green_duration": self.next_green_duration,
            "next_priority_score": self.next_priority_score,
            "signal_states": dict(self.signal_states),
            "priorities": priorities,
            "cycles_completed": self.cycles_completed,
            "emergency": self.get_emergency_state()
        }
