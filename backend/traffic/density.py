from typing import Dict, Tuple, List
from collections import deque


class DensityCalculator:
    """
    Computes traffic density category (LOW, MEDIUM, HIGH) and percentage.
    Implements moving window smoothing to avoid flickering.
    """
    def __init__(self, low_max: int = 5, med_max: int = 10, max_capacity: int = 20, window_size: int = 5):
        self.low_max = low_max
        self.med_max = med_max
        self.max_capacity = max(max_capacity, 1)
        self.window_size = window_size

        self.history: Dict[str, deque] = {
            "NORTH": deque(maxlen=window_size),
            "SOUTH": deque(maxlen=window_size),
            "EAST": deque(maxlen=window_size),
            "WEST": deque(maxlen=window_size),
        }

    def update_thresholds(self, low_max: int, med_max: int, max_capacity: int = 20):
        self.low_max = low_max
        self.med_max = med_max
        self.max_capacity = max(max_capacity, 1)

    def calculate_level_and_pct(self, count: float) -> Tuple[str, float]:
        pct = min(100.0, (count / self.max_capacity) * 100.0)
        if count <= self.low_max:
            level = "LOW"
        elif count <= self.med_max:
            level = "MEDIUM"
        else:
            level = "HIGH"
        return level, round(pct, 1)

    def update(self, counts: Dict[str, int]) -> Dict[str, Tuple[str, float]]:
        """
        Takes raw vehicle counts per direction.
        Returns: { 'NORTH': ('LOW', 15.0), ... }
        """
        results = {}
        for direction, count in counts.items():
            if direction not in self.history:
                self.history[direction] = deque(maxlen=self.window_size)
            self.history[direction].append(count)
            avg_count = sum(self.history[direction]) / len(self.history[direction])
            results[direction] = self.calculate_level_and_pct(avg_count)
        return results
