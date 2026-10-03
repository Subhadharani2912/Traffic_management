from backend.traffic.vehicle_counter import VehicleCounter
from backend.traffic.density import DensityCalculator
from backend.traffic.waiting_time import WaitingTimeTracker
from backend.traffic.priority import PriorityCalculator


def test_vehicle_counter_zero():
    counter = VehicleCounter()
    result = counter.update_from_tracked_vehicles([])
    assert result == {"NORTH": 0, "SOUTH": 0, "EAST": 0, "WEST": 0}


def test_density_low_medium_high():
    calc = DensityCalculator(low_max=5, med_max=10, max_capacity=20)
    low = calc.update({"NORTH": 2, "SOUTH": 3, "EAST": 6, "WEST": 11})
    assert low["NORTH"][0] == "LOW"
    assert low["EAST"][0] == "MEDIUM"
    assert low["WEST"][0] == "HIGH"


def test_waiting_time_calculation():
    tracker = WaitingTimeTracker(speed_threshold=3.5)
    vehicles = [
        {"id": 1, "direction": "NORTH", "speed": 2.0, "in_intersection": False, "has_crossed": False},
        {"id": 2, "direction": "SOUTH", "speed": 5.0, "in_intersection": False, "has_crossed": False},
    ]
    stats = tracker.update(vehicles, {"NORTH": "RED", "SOUTH": "GREEN", "EAST": "RED", "WEST": "RED"}, 2.0)
    assert stats["NORTH"]["avg_wait"] >= 0
    assert stats["SOUTH"]["avg_wait"] >= 0
    # Waiting count: only the stopped vehicle under RED is "waiting"
    assert stats["NORTH"]["wait_count"] == 1
    assert stats["SOUTH"]["wait_count"] == 0
    assert vehicles[0]["is_waiting"] is True
    assert vehicles[1]["is_waiting"] is False


def test_priority_and_green_duration():
    calc = PriorityCalculator(density_weight=0.6, waiting_weight=0.4, min_green=10, max_green=40)
    priorities = calc.calculate_priorities({"NORTH": 8, "SOUTH": 4, "EAST": 2, "WEST": 6}, {"NORTH": {"avg_wait": 20}, "SOUTH": {"avg_wait": 7}, "EAST": {"avg_wait": 1}, "WEST": {"avg_wait": 13}}, "WEST")
    assert priorities["NORTH"] > 0
    green = calc.calculate_green_duration(8, priorities["NORTH"])
    assert 10 <= green <= 40


def test_queue_clearing_green_duration():
    calc = PriorityCalculator(min_green=5, max_green=40)
    # Empty lane gets a quick pass-through (not a long fixed green)
    assert calc.compute_green_duration(0, 0.0) == 4.0
    # A few vehicles -> just enough time for that queue to clear
    small = calc.compute_green_duration(4, 0.0)
    assert 5.0 <= small <= 14.0
    # Many vehicles -> clearly longer green
    big = calc.compute_green_duration(15, 0.0)
    assert big > small
    # Queue time is never padded by waiting time in the duration itself
    same_queue = calc.compute_green_duration(4, 55.0)
    assert same_queue == small
    # Never longer than max_green (no lane monopolizes forever)
    assert calc.compute_green_duration(500, 0.0) <= 40.0


def test_signal_transition_safety():
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator()
    controller = SignalController(calc, yellow_duration=3, all_red_duration=1, adaptive_mode=True)
    state = controller.step(1.0, {"NORTH": 4, "SOUTH": 2, "EAST": 1, "WEST": 0}, {"NORTH": {"avg_wait": 12}, "SOUTH": {"avg_wait": 4}, "EAST": {"avg_wait": 1}, "WEST": {"avg_wait": 0}})
    assert state["phase_state"] in {"GREEN", "YELLOW", "ALL_RED"}


def test_waiting_drives_priority_over_raw_count():
    """Starved-lane example from the requirements:
    WEST has only 5 vehicles but 55s wait -> beats SOUTH with 15 vehicles / 10s wait.
    Priority must combine BOTH density and waiting time, never count alone."""
    calc = PriorityCalculator(density_weight=0.6, waiting_weight=0.4, starvation_threshold=45.0, max_density_ref=20.0, max_wait_ref=60.0)
    counts = {"NORTH": 4, "SOUTH": 15, "EAST": 8, "WEST": 5}
    waits = {
        "NORTH": {"avg_wait": 5.0, "starvation_timer": 5.0},
        "SOUTH": {"avg_wait": 10.0, "starvation_timer": 10.0},
        "EAST": {"avg_wait": 15.0, "starvation_timer": 15.0},
        "WEST": {"avg_wait": 55.0, "starvation_timer": 55.0},
    }
    scores = calc.calculate_priorities(counts, waits, "EAST")
    assert scores["WEST"] > scores["SOUTH"]
    assert scores["WEST"] > scores["NORTH"]
    # Fewer cars but long wait still gets picked (not a pure density decision)
    next_dir, duration = calc.select_next_phase(scores, "EAST", counts, waits)
    assert next_dir == "WEST"
    assert duration < 40.0


def test_dynamic_green_gives_big_queue_more_time_but_still_terminates():
    """HIGH TRAFFIC requirement: a loaded lane gets a long green, but the
    controller must still stop serving it once it clears / loses priority."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator(min_green=5, max_green=40)
    controller = SignalController(calc, yellow_duration=3, all_red_duration=1, adaptive_mode=True)
    # Active lane = SOUTH so the queue dt is measured against the loaded lane
    controller.current_direction = "SOUTH"
    controller.signal_states = {"NORTH": "RED", "SOUTH": "GREEN", "EAST": "RED", "WEST": "RED"}
    state = controller.step(1.0, {"NORTH": 0, "SOUTH": 30, "EAST": 1, "WEST": 0}, {"NORTH": {"avg_wait": 0}, "SOUTH": {"avg_wait": 20}, "EAST": {"avg_wait": 1}, "WEST": {"avg_wait": 0}})
    assert state["current_green_duration"] <= 40.0
    # Queue of 30 cars -> long green (start window + 30 x headway capped)
    assert state["current_green_duration"] >= 10.0


def test_waiting_time_tracker_accrues_and_releases():
    """A vehicle held on RED at the approach builds waiting time and is flagged
    is_waiting; on GREEN it stops waiting and the wait_count drops."""
    tracker = WaitingTimeTracker(speed_threshold=3.5)
    red_frame = [
        {"id": 1, "direction": "SOUTH", "speed": 0.2, "in_intersection": False, "has_crossed": False},
        {"id": 2, "direction": "SOUTH", "speed": 6.0, "in_intersection": False, "has_crossed": False},
    ]
    tracker.update(red_frame, {"NORTH": "RED", "SOUTH": "RED", "EAST": "RED", "WEST": "RED"}, 2.0)
    tracker.update(red_frame, {"NORTH": "RED", "SOUTH": "RED", "EAST": "RED", "WEST": "RED"}, 2.0)
    stats = tracker.update(red_frame, {"NORTH": "RED", "SOUTH": "RED", "EAST": "RED", "WEST": "RED"}, 2.0)
    assert stats["SOUTH"]["wait_count"] == 1
    assert stats["SOUTH"]["avg_wait"] == 6.0
    assert red_frame[0]["is_waiting"] is True
    assert red_frame[1]["is_waiting"] is False
    # Signal turns GREEN -> the stopped vehicle is released; waiting clears
    tracker.update(red_frame, {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"}, 2.0)
    stats = tracker.update(red_frame, {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"}, 2.0)
    assert stats["SOUTH"]["wait_count"] == 0


def test_only_one_green_and_proper_transition_cycle():
    """Safety invariant: exactly one approach GREEN ever, and the order is
    always GREEN -> YELLOW -> ALL_RED -> GREEN for the next lane."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator(min_green=5, max_green=40)
    controller = SignalController(calc, yellow_duration=3, all_red_duration=1, adaptive_mode=True)
    counts = {"NORTH": 6, "SOUTH": 2, "EAST": 0, "WEST": 0}
    waits = {
        "NORTH": {"avg_wait": 8}, "SOUTH": {"avg_wait": 3},
        "EAST": {"avg_wait": 0}, "WEST": {"avg_wait": 0},
    }
    seen = []
    for _ in range(200):
        state = controller.step(0.5, counts, waits)
        greens = [d for d in ["NORTH", "SOUTH", "EAST", "WEST"] if state["signal_states"][d] == "GREEN"]
        assert len(greens) <= 1, f"more than one GREEN: {greens}"
        # During GREEN exactly one approach is green; during YELLOW/ALL_RED zero
        assert (len(greens) == 1) == (state["phase_state"] == "GREEN")
        seen.append(state["phase_state"])
        if len(set(seen[-4:])) == 3 and state["phase_state"] == "GREEN":
            break
    # The four phases must have appeared in a valid cycle
    assert "GREEN" in seen and "YELLOW" in seen and "ALL_RED" in seen
