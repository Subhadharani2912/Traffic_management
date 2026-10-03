from typing import Dict, Set, Any, List


class VehicleCounter:
    """
    Maintains active and cumulative vehicle counts per direction without double counting.
    Tracks vehicle states across frames.
    """
    def __init__(self):
        self.active_counts: Dict[str, int] = {
            "NORTH": 0,
            "SOUTH": 0,
            "EAST": 0,
            "WEST": 0
        }
        self.passed_counts: Dict[str, int] = {
            "NORTH": 0,
            "SOUTH": 0,
            "EAST": 0,
            "WEST": 0
        }
        # Track IDs seen in each direction
        self.seen_track_ids: Dict[str, Set[int]] = {
            "NORTH": set(),
            "SOUTH": set(),
            "EAST": set(),
            "WEST": set()
        }
        self.total_passed: int = 0

    def reset_counts(self):
        self.active_counts = {"NORTH": 0, "SOUTH": 0, "EAST": 0, "WEST": 0}
        self.seen_track_ids = {"NORTH": set(), "SOUTH": set(), "EAST": set(), "WEST": set()}

    def update_from_tracked_vehicles(self, tracked_vehicles: List[Dict[str, Any]]):
        """
        tracked_vehicles: list of active vehicles with:
        { 'id': int, 'direction': str, 'in_intersection': bool, 'has_crossed': bool, ... }
        """
        temp_counts = {"NORTH": 0, "SOUTH": 0, "EAST": 0, "WEST": 0}

        for veh in tracked_vehicles:
            direction = veh.get("direction")
            in_intersection = veh.get("in_intersection", False)
            has_crossed = veh.get("has_crossed", False)
            track_id = veh.get("id")

            if direction in temp_counts and not in_intersection and not has_crossed:
                temp_counts[direction] += 1
                if track_id is not None:
                    self.seen_track_ids[direction].add(track_id)

            if has_crossed and veh.get("counted_as_passed", False) is False:
                veh["counted_as_passed"] = True
                if veh.get("crossed_signal", "GREEN") == "GREEN" and direction in self.passed_counts:
                    self.passed_counts[direction] += 1
                    self.total_passed += 1

        self.active_counts = temp_counts
        return self.active_counts

    def get_counts(self) -> Dict[str, int]:
        return dict(self.active_counts)

    def get_total_active(self) -> int:
        return sum(self.active_counts.values())

    def get_total_passed(self) -> int:
        return self.total_passed
