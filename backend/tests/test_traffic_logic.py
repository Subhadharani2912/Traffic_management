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


# ============================================================================
# PHASE 2: EMERGENCY VEHICLE DETECTION & PREEMPTION UNIT TESTS
# ============================================================================

def test_emergency_preemption_north():
    """Emergency preemption safely routes green signal to NORTH."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator(min_green=5, max_green=40)
    controller = SignalController(calc, yellow_duration=3.0, all_red_duration=1.0)
    controller.current_direction = "SOUTH"
    controller.signal_states = {"NORTH": "RED", "SOUTH": "GREEN", "EAST": "RED", "WEST": "RED"}

    controller.preempt_emergency(direction="NORTH", duration=15.0, emergency_type="ambulance")
    counts = {"NORTH": 0, "SOUTH": 20, "EAST": 5, "WEST": 5}
    waits = {d: {"avg_wait": 0.0} for d in ["NORTH", "SOUTH", "EAST", "WEST"]}

    # Advance through clearance (3s YELLOW + 1s ALL_RED)
    for _ in range(10):
        controller.step(0.5, counts, waits)

    state = controller.get_state()
    assert state["current_direction"] == "NORTH"
    assert state["phase_state"] == "GREEN"
    assert state["signal_states"]["NORTH"] == "GREEN"
    assert state["emergency"]["active"] is True
    assert state["emergency"]["direction"] == "NORTH"
    assert state["emergency"]["type"] == "ambulance"


def test_emergency_preemption_south():
    """Emergency preemption safely routes green signal to SOUTH."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator(min_green=5, max_green=40)
    controller = SignalController(calc, yellow_duration=3.0, all_red_duration=1.0)
    controller.current_direction = "NORTH"
    controller.signal_states = {"NORTH": "GREEN", "SOUTH": "RED", "EAST": "RED", "WEST": "RED"}

    controller.preempt_emergency(direction="SOUTH", duration=15.0, emergency_type="ambulance")
    counts = {"NORTH": 10, "SOUTH": 0, "EAST": 0, "WEST": 0}
    waits = {d: {"avg_wait": 0.0} for d in ["NORTH", "SOUTH", "EAST", "WEST"]}

    for _ in range(10):
        controller.step(0.5, counts, waits)

    state = controller.get_state()
    assert state["current_direction"] == "SOUTH"
    assert state["phase_state"] == "GREEN"
    assert state["signal_states"]["SOUTH"] == "GREEN"
    assert state["emergency"]["active"] is True


def test_emergency_preemption_east():
    """Emergency preemption safely routes green signal to EAST."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator(min_green=5, max_green=40)
    controller = SignalController(calc, yellow_duration=3.0, all_red_duration=1.0)
    controller.current_direction = "WEST"
    controller.signal_states = {"NORTH": "RED", "SOUTH": "RED", "EAST": "RED", "WEST": "GREEN"}

    controller.preempt_emergency(direction="EAST", duration=15.0, emergency_type="fire_truck")
    counts = {"NORTH": 5, "SOUTH": 5, "EAST": 0, "WEST": 10}
    waits = {d: {"avg_wait": 0.0} for d in ["NORTH", "SOUTH", "EAST", "WEST"]}

    for _ in range(10):
        controller.step(0.5, counts, waits)

    state = controller.get_state()
    assert state["current_direction"] == "EAST"
    assert state["phase_state"] == "GREEN"
    assert state["signal_states"]["EAST"] == "GREEN"
    assert state["emergency"]["active"] is True
    assert state["emergency"]["type"] == "fire_truck"


def test_emergency_preemption_west():
    """Emergency preemption safely routes green signal to WEST."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator(min_green=5, max_green=40)
    controller = SignalController(calc, yellow_duration=3.0, all_red_duration=1.0)
    controller.current_direction = "EAST"
    controller.signal_states = {"NORTH": "RED", "SOUTH": "RED", "EAST": "GREEN", "WEST": "RED"}

    controller.preempt_emergency(direction="WEST", duration=15.0, emergency_type="police")
    counts = {"NORTH": 5, "SOUTH": 5, "EAST": 10, "WEST": 0}
    waits = {d: {"avg_wait": 0.0} for d in ["NORTH", "SOUTH", "EAST", "WEST"]}

    for _ in range(10):
        controller.step(0.5, counts, waits)

    state = controller.get_state()
    assert state["current_direction"] == "WEST"
    assert state["phase_state"] == "GREEN"
    assert state["signal_states"]["WEST"] == "GREEN"
    assert state["emergency"]["active"] is True
    assert state["emergency"]["type"] == "police"


def test_emergency_safe_yellow_transition():
    """Conflicting active green must first switch to YELLOW (3.0s) and NEVER jump directly to RED/GREEN."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator()
    controller = SignalController(calc, yellow_duration=3.0, all_red_duration=1.0)
    controller.current_direction = "EAST"
    controller.signal_states = {"NORTH": "RED", "SOUTH": "RED", "EAST": "GREEN", "WEST": "RED"}

    controller.preempt_emergency(direction="NORTH", duration=15.0, emergency_type="ambulance")
    # Immediately after preemption call, EAST must be YELLOW
    assert controller.signal_states["EAST"] == "YELLOW"
    assert controller.phase_state.value == "YELLOW"
    assert controller.signal_states["NORTH"] == "RED"

    # Step 1.5 seconds: must still be in YELLOW clearance
    counts = {d: 0 for d in ["NORTH", "SOUTH", "EAST", "WEST"]}
    waits = {d: {"avg_wait": 0.0} for d in ["NORTH", "SOUTH", "EAST", "WEST"]}
    controller.step(1.5, counts, waits)
    assert controller.phase_state.value == "YELLOW"
    assert controller.signal_states["EAST"] == "YELLOW"
    assert controller.signal_states["NORTH"] == "RED"


def test_emergency_all_red_before_green():
    """All signals must be RED during all-red clearance before the emergency approach turns GREEN."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator()
    controller = SignalController(calc, yellow_duration=3.0, all_red_duration=1.0)
    controller.current_direction = "EAST"
    controller.signal_states = {"NORTH": "RED", "SOUTH": "RED", "EAST": "GREEN", "WEST": "RED"}

    controller.preempt_emergency(direction="NORTH", duration=15.0, emergency_type="ambulance")
    counts = {d: 0 for d in ["NORTH", "SOUTH", "EAST", "WEST"]}
    waits = {d: {"avg_wait": 0.0} for d in ["NORTH", "SOUTH", "EAST", "WEST"]}

    # Advance through 3.0s YELLOW
    controller.step(3.0, counts, waits)

    # Now in ALL_RED clearance (1.0s duration)
    assert controller.phase_state.value == "ALL_RED"
    for d in ["NORTH", "SOUTH", "EAST", "WEST"]:
        assert controller.signal_states[d] == "RED", f"Signal {d} is not RED during ALL_RED clearance"
    assert controller.signal_states["NORTH"] == "RED"

    # Advance past 1.0s ALL_RED
    controller.step(1.1, counts, waits)
    assert controller.phase_state.value == "GREEN"
    assert controller.signal_states["NORTH"] == "GREEN"


def test_emergency_only_one_green_safety_invariant():
    """Safety Invariant: At no point during emergency transitions can multiple green lights coexist."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator(min_green=5, max_green=40)
    controller = SignalController(calc, yellow_duration=3.0, all_red_duration=1.0)
    controller.current_direction = "SOUTH"
    controller.signal_states = {"NORTH": "RED", "SOUTH": "GREEN", "EAST": "RED", "WEST": "RED"}

    controller.preempt_emergency(direction="WEST", duration=10.0, emergency_type="fire_truck")
    counts = {"NORTH": 5, "SOUTH": 5, "EAST": 5, "WEST": 5}
    waits = {d: {"avg_wait": 10.0} for d in ["NORTH", "SOUTH", "EAST", "WEST"]}

    # Simulate 50 discrete time steps through preemption and clearance
    for _ in range(50):
        state = controller.step(0.4, counts, waits)
        green_count = sum(1 for d in ["NORTH", "SOUTH", "EAST", "WEST"] if state["signal_states"][d] == "GREEN")
        assert green_count <= 1, f"Safety violation: multiple greens detected: {state['signal_states']}"
        if state["phase_state"] == "GREEN":
            assert green_count == 1
        elif state["phase_state"] in ("YELLOW", "ALL_RED"):
            assert green_count == 0


def test_normal_adaptive_resumes_after_emergency():
    """Once preemption timer expires, emergency clears and normal adaptive signal control safely resumes."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator(min_green=5, max_green=40)
    controller = SignalController(calc, yellow_duration=2.0, all_red_duration=1.0)
    controller.current_direction = "NORTH"
    controller.phase_state = controller.phase_state.GREEN
    controller.signal_states = {"NORTH": "GREEN", "SOUTH": "RED", "EAST": "RED", "WEST": "RED"}

    # Preempt NORTH for 4.0 seconds
    controller.preempt_emergency(direction="NORTH", duration=4.0, emergency_type="ambulance")
    counts = {"NORTH": 0, "SOUTH": 30, "EAST": 2, "WEST": 0}
    waits = {"NORTH": {"avg_wait": 0}, "SOUTH": {"avg_wait": 25}, "EAST": {"avg_wait": 0}, "WEST": {"avg_wait": 0}}

    # Step through 4.0 seconds of emergency green
    controller.step(4.5, counts, waits)

    # Preemption timer expired -> emergency is cleared and cycle moves to yellow
    assert controller.emergency_active is False
    assert controller.emergency_status in ("CLEARED", "IDLE")

    # Step through clearance (2s yellow + 1s all-red)
    controller.step(2.0, counts, waits)
    controller.step(1.5, counts, waits)

    # Next direction should be picked adaptively (SOUTH has highest traffic & wait)
    state = controller.get_state()
    assert state["current_direction"] == "SOUTH"
    assert state["phase_state"] == "GREEN"
    assert state["signal_states"]["SOUTH"] == "GREEN"


def test_duplicate_emergency_no_repeated_preemption():
    """Repeated triggers for the same active emergency extend/maintain duration without corrupting phases."""
    from backend.traffic.signal_controller import SignalController
    calc = PriorityCalculator(min_green=5, max_green=40)
    controller = SignalController(calc, yellow_duration=3.0, all_red_duration=1.0)
    controller.current_direction = "NORTH"
    controller.phase_state = controller.phase_state.GREEN
    controller.signal_states = {"NORTH": "GREEN", "SOUTH": "RED", "EAST": "RED", "WEST": "RED"}

    # First preemption call
    controller.preempt_emergency(direction="NORTH", duration=15.0, emergency_type="ambulance")
    assert controller.current_direction == "NORTH"
    assert controller.signal_states["NORTH"] == "GREEN"

    # Repeated identical call must not switch to YELLOW or reset active status
    controller.preempt_emergency(direction="NORTH", duration=20.0, emergency_type="ambulance")
    assert controller.current_direction == "NORTH"
    assert controller.signal_states["NORTH"] == "GREEN"
    assert controller.emergency_timer_remaining == 20.0
    assert controller.phase_state.value == "GREEN"


def test_emergency_multi_frame_confirmation():
    """Anti-flicker test: Single-frame detection must NOT trigger preemption until 5 consecutive frames confirm."""
    import time
    from backend.detection.tracker import TrackedVehicle

    vehicle = TrackedVehicle(
        track_id=101,
        class_name="car",
        bbox=[100, 100, 200, 200],
        confidence=0.85,
        timestamp=time.time()
    )
    vehicle.direction = "NORTH"

    # Frame 1 to 4: detected, but fewer than 5 consecutive frames
    for f in range(1, 5):
        became_active = vehicle.update_emergency(
            is_detected=True,
            emergency_type="ambulance",
            confidence=0.88,
            confirmation_frames=5
        )
        assert became_active is False
        assert vehicle.emergency_active is False
        assert vehicle.emergency_detection_frames == f

    # False-alarm flicker: detection drops on frame 5 -> resets frame counter
    became_active = vehicle.update_emergency(
        is_detected=False,
        confirmation_frames=5
    )
    assert became_active is False
    assert vehicle.emergency_active is False
    assert vehicle.emergency_detection_frames == 0

    # Now 5 consecutive real frames
    for f in range(1, 5):
        vehicle.update_emergency(is_detected=True, emergency_type="ambulance", confidence=0.9, confirmation_frames=5)
        assert vehicle.emergency_active is False

    # 5th frame reaches confirmation threshold
    became_active = vehicle.update_emergency(is_detected=True, emergency_type="ambulance", confidence=0.9, confirmation_frames=5)
    assert became_active is True
    assert vehicle.emergency_active is True
    assert vehicle.emergency_type == "ambulance"


# ============================================================================
# PHASE 3: EMERGENCY MODEL VALIDATION & INTEGRATION TESTS
# ============================================================================

def test_emergency_detector_load_and_dynamic_classes():
    """Verify VehicleDetector loads emergency_best.pt and resolves classes dynamically."""
    from backend.detection.detector import VehicleDetector
    detector = VehicleDetector(emergency_model_path="models/emergency_best.pt")
    assert detector.has_emergency_model is True
    assert "emergency_best.pt" in detector.emergency_model_status
    assert hasattr(detector, "active_emergency_map")
    assert "ambulance" in detector.active_emergency_map.values()


def test_emergency_detector_missing_fallback():
    """Verify VehicleDetector cleanly falls back when model file is missing without crashing."""
    import numpy as np
    from backend.detection.detector import VehicleDetector
    detector = VehicleDetector(emergency_model_path="models/non_existent_weights.pt")
    assert detector.has_emergency_model is False
    assert "Awaiting fine-tuned model" in detector.emergency_model_status
    dummy_frame = np.zeros((300, 300, 3), dtype=np.uint8)
    detections = detector.detect_emergency(dummy_frame)
    assert detections == []


def test_tracker_standalone_emergency_detection():
    """Verify tracker manages emergency vehicle even when primary detector misses it."""
    import time
    from backend.detection.tracker import VehicleTrackerManager
    from backend.traffic.lane_manager import LaneManager

    tracker = VehicleTrackerManager(emergency_confirmation_frames=3)
    lane_mgr = LaneManager()

    # Feed 3 consecutive frames with an emergency ambulance detection in the SOUTH approach
    em_detection = [{
        "bbox": [550, 650, 650, 750],
        "class_id": 0,
        "class_name": "ambulance",
        "confidence": 0.92,
        "center": (600, 700)
    }]

    for _ in range(2):
        tracker.update_with_yolo_tracks(
            None, lane_mgr, 1280, 720, time.time(),
            signal_states={"SOUTH": "RED"},
            emergency_detections=em_detection
        )
        assert tracker.get_active_emergency() is None

    # 3rd frame confirms emergency
    tracker.update_with_yolo_tracks(
        None, lane_mgr, 1280, 720, time.time(),
        signal_states={"SOUTH": "RED"},
        emergency_detections=em_detection
    )
    confirmed = tracker.get_active_emergency()
    assert confirmed is not None
    assert confirmed.emergency_active is True
    assert confirmed.emergency_type == "ambulance"
    assert confirmed.direction == "SOUTH"


def test_end_to_end_emergency_detection_preemption_flow():
    """Full pipeline: 5 confirmed video frames trigger safe signal preemption to SOUTH."""
    import time
    from backend.detection.tracker import VehicleTrackerManager
    from backend.traffic.lane_manager import LaneManager
    from backend.traffic.priority import PriorityCalculator
    from backend.traffic.signal_controller import SignalController

    calc = PriorityCalculator(min_green=5, max_green=40)
    controller = SignalController(calc, yellow_duration=3.0, all_red_duration=1.0)
    controller.current_direction = "NORTH"
    controller.signal_states = {"NORTH": "GREEN", "SOUTH": "RED", "EAST": "RED", "WEST": "RED"}

    tracker = VehicleTrackerManager(emergency_confirmation_frames=5)
    lane_mgr = LaneManager()

    em_detection = [{
        "bbox": [550, 650, 650, 750],
        "class_id": 0,
        "class_name": "ambulance",
        "confidence": 0.95,
        "center": (600, 700)
    }]

    # Step 5 consecutive frames through tracker
    for f in range(5):
        tracker.update_with_yolo_tracks(
            None, lane_mgr, 1280, 720, time.time(),
            signal_states=controller.get_signal_states(),
            emergency_detections=em_detection
        )

    confirmed = tracker.get_active_emergency()
    assert confirmed is not None
    assert confirmed.direction == "SOUTH"

    # Preempt controller
    controller.preempt_emergency(
        direction=confirmed.direction,
        duration=15.0,
        emergency_type=confirmed.emergency_type,
        vehicle_id=confirmed.id,
        confidence=confirmed.emergency_confidence
    )

    # Immediately after preemption, NORTH (current green) must yield to YELLOW
    assert controller.signal_states["NORTH"] == "YELLOW"
    assert controller.signal_states["SOUTH"] == "RED"

    # Step through clearance (3s yellow + 1s all-red)
    counts = {"NORTH": 5, "SOUTH": 0, "EAST": 0, "WEST": 0}
    waits = {d: {"avg_wait": 0.0} for d in ["NORTH", "SOUTH", "EAST", "WEST"]}
    controller.step(3.0, counts, waits)
    assert controller.phase_state.value == "ALL_RED"
    assert controller.signal_states["SOUTH"] == "RED"

    controller.step(1.1, counts, waits)
    assert controller.phase_state.value == "GREEN"
    assert controller.signal_states["SOUTH"] == "GREEN"
    assert controller.signal_states["NORTH"] == "RED"
    assert controller.emergency_active is True


