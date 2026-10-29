from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any


class DirectionMetrics(BaseModel):
    direction: str  # 'NORTH', 'SOUTH', 'EAST', 'WEST'
    count: int = 0
    waiting_count: int = 0
    density_level: str = "LOW"  # 'LOW', 'MEDIUM', 'HIGH'
    density_percent: float = 0.0
    avg_waiting_time: float = 0.0
    max_waiting_time: float = 0.0
    signal_state: str = "RED"  # 'RED', 'YELLOW', 'GREEN'
    priority_score: float = 0.0
    
    starvation_timer: float = 0.0


class EmergencyState(BaseModel):
    active: bool = False
    vehicle_id: Optional[int] = None
    type: Optional[str] = None  # 'ambulance', 'fire_truck', 'police'
    direction: Optional[str] = None  # 'NORTH', 'SOUTH', 'EAST', 'WEST'
    confidence: float = 0.0
    duration: float = 0.0
    timer_remaining: float = 0.0
    status: str = "IDLE"  # 'IDLE', 'TRANSITIONING', 'PREEMPTED', 'CLEARED'


class TrafficStateResponse(BaseModel):
    session_id: Optional[int] = None
    mode: str = "simulation"  # 'simulation' or 'video'
    active_direction: str = "NORTH"
    active_signal_state: str = "GREEN"  # 'GREEN', 'YELLOW', 'ALL_RED'
    current_green_time_assigned: float = 15.0
    remaining_green_time: float = 15.0
    yellow_remaining: float = 0.0
    next_direction: str = "SOUTH"
    next_priority_score: float = 0.0
    total_active_vehicles: int = 0
    total_waiting_vehicles: int = 0
    total_passed_vehicles: int = 0
    system_avg_waiting_time: float = 0.0
    system_max_waiting_time: float = 0.0
    fps: float = 0.0
    adaptive_mode: bool = True
    directions: Dict[str, DirectionMetrics]
    tracked_vehicles: List[Dict[str, Any]] = []
    emergency: Optional[EmergencyState] = Field(default_factory=EmergencyState)
    timestamp: str


class SessionSummary(BaseModel):
    id: int
    session_name: str
    mode: str
    source_name: Optional[str]
    started_at: str
    ended_at: Optional[str]
    total_vehicles: int
    total_cycles: int
    avg_waiting_time: float
    max_waiting_time: float
    avg_green_duration: float


class SystemLogEntry(BaseModel):
    id: int
    timestamp: str
    level: str
    category: str
    message: str
    details: Optional[str]
