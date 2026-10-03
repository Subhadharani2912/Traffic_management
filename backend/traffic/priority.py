from typing import Dict, Tuple, Any


class PriorityCalculator:
    """
    Computes priority scores for each direction combining:
    1. Normalized vehicle density / count (density_weight)
    2. Normalized waiting time (waiting_weight)
    3. Starvation prevention penalty/boost

    Also computes the adaptive green time duration for the selected direction.
    """
    def __init__(
        self,
        density_weight: float = 0.6,
        waiting_weight: float = 0.4,
        starvation_threshold: float = 45.0,
        min_green: int = 5,
        max_green: int = 40,
        max_density_ref: float = 20.0,
        max_wait_ref: float = 60.0,
        headway_seconds: float = 2.2,
        start_window_seconds: float = 2.5
    ):
        self.density_weight = density_weight
        self.waiting_weight = waiting_weight
        self.starvation_threshold = starvation_threshold
        self.min_green = min_green
        self.max_green = max_green
        self.max_density_ref = max_density_ref
        self.max_wait_ref = max_wait_ref
        self.headway_seconds = headway_seconds
        self.start_window_seconds = start_window_seconds

    def update_params(
        self,
        density_weight: float,
        waiting_weight: float,
        starvation_threshold: float,
        min_green: int,
        max_green: int,
        headway_seconds: float = 2.2,
        start_window_seconds: float = 2.5
    ):
        self.density_weight = density_weight
        self.waiting_weight = waiting_weight
        self.starvation_threshold = starvation_threshold
        self.min_green = min_green
        self.max_green = max_green
        self.headway_seconds = headway_seconds
        self.start_window_seconds = start_window_seconds

    def calculate_priorities(
        self,
        counts: Dict[str, int],
        waiting_stats: Dict[str, Dict[str, float]],
        current_green_direction: str
    ) -> Dict[str, float]:
        """
        Calculates priority score (0.0 to 100.0+) for each direction.
        Applies starvation boost if a direction has waited longer than starvation_threshold.
        """
        scores = {}
        for direction in ["NORTH", "SOUTH", "EAST", "WEST"]:
            count = counts.get(direction, 0)
            stats = waiting_stats.get(direction, {})
            avg_wait = stats.get("avg_wait", 0.0)
            starvation_time = stats.get("starvation_timer", 0.0)

            # Normalization (0.0 to 1.0)
            norm_density = min(1.0, count / self.max_density_ref)
            norm_wait = min(1.0, avg_wait / self.max_wait_ref)

            base_score = (self.density_weight * norm_density) + (self.waiting_weight * norm_wait)
            score_100 = base_score * 100.0

            # Starvation prevention boost:
            # If direction has waited without green for longer than threshold, add urgency
            if direction != current_green_direction and starvation_time > self.starvation_threshold:
                overdue = starvation_time - self.starvation_threshold
                # Exponential/linear starvation penalty added to priority
                starvation_boost = min(60.0, overdue * 1.5)
                score_100 += starvation_boost

            # If count is 0 and starvation is low, keep score minimal
            if count == 0 and starvation_time < self.starvation_threshold:
                score_100 = min(score_100, 5.0)

            scores[direction] = round(score_100, 2)

        return scores

    def select_next_phase(
        self,
        priorities: Dict[str, float],
        current_green_direction: str,
        counts: Dict[str, int],
        waiting_stats: Dict[str, Dict[str, float]] = None
    ) -> Tuple[str, float]:
        """
        Selects next green direction. Prefers candidate other than current; on
        ties the next clockwise neighbor wins so the signal rotates fairly
        through all four lanes (NORTH -> EAST -> SOUTH -> WEST).
        Returns (next_direction, green_duration_seconds)
        """
        base = ["NORTH", "EAST", "SOUTH", "WEST"]
        if current_green_direction in base:
            idx = base.index(current_green_direction)
            # All other lanes in clockwise order, current EXCLUDED (it must lose its turn)
            rotation = base[idx + 1:] + base[:idx]
        else:
            rotation = base

        best_dir = None
        best_score = -1.0
        for d in rotation:
            s = priorities.get(d, 0.0)
            # strict '>' so the first candidate in rotation wins ties (fair turn)
            if s > best_score:
                best_score = s
                best_dir = d

        if best_dir is None:
            best_dir = current_green_direction

        wait = 0.0
        if waiting_stats is not None:
            wait = waiting_stats.get(best_dir, {}).get("avg_wait", 0.0)
        duration = self.compute_green_duration(counts.get(best_dir, 0), wait)
        return best_dir, duration

    def compute_green_duration(self, vehicle_count: int, avg_wait: float = 0.0) -> float:
        """
        Queue-clearing green time: gives the active lane only as much green as
        its current queue actually needs to cross the intersection:
            green = start window (first vehicle starts) + queued vehicles x headway
        - A few vehicles -> a short green (no wasted time for free lanes).
        - Many vehicles -> a long green, capped at max_green_time so no lane
          monopolizes the junction (the next most loaded lane keeps its turn).
        - An empty lane with nobody waiting gets a quick pass-through so the
          signal keeps rotating instead of holding everyone else up.
        Waiting time is used for choosing WHICH lane goes next, not for padding
        these timer values.
        """
        max_g = float(self.max_green)
        min_g = float(self.min_green)

        if vehicle_count <= 0 and avg_wait < 1.0:
            return 4.0  # empty lane: short pass-through, keep rotating

        cross_sec = max(1, int(vehicle_count)) * float(self.headway_seconds)
        need = float(self.start_window_seconds) + cross_sec
        return round(min(max_g, max(min_g, need)), 1)

    def calculate_green_duration(self, vehicle_count: int, priority_score: float) -> float:
        """
        Preview duration used by callers that only have a priority score.
        Delegates to the queue-clearing formula.
        """
        return self.compute_green_duration(vehicle_count, 0.0)
