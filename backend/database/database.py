import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.config import DB_PATH


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_name TEXT NOT NULL,
        mode TEXT NOT NULL, -- 'video' or 'simulation'
        source_name TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ended_at TIMESTAMP,
        total_vehicles INTEGER DEFAULT 0,
        total_cycles INTEGER DEFAULT 0,
        avg_waiting_time REAL DEFAULT 0.0,
        max_waiting_time REAL DEFAULT 0.0,
        avg_green_duration REAL DEFAULT 0.0
    )
    """)

    # Periodic Traffic Snapshots (every few seconds or cycle)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traffic_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        north_count INTEGER DEFAULT 0,
        south_count INTEGER DEFAULT 0,
        east_count INTEGER DEFAULT 0,
        west_count INTEGER DEFAULT 0,
        north_density TEXT,
        south_density TEXT,
        east_density TEXT,
        west_density TEXT,
        north_wait REAL DEFAULT 0.0,
        south_wait REAL DEFAULT 0.0,
        east_wait REAL DEFAULT 0.0,
        west_wait REAL DEFAULT 0.0,
        current_green TEXT,
        green_duration INTEGER DEFAULT 0,
        priority_scores TEXT, -- JSON dict of scores
        FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
    )
    """)

    # Signal Phase Changes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS signal_phases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        phase_direction TEXT NOT NULL,
        from_state TEXT NOT NULL,
        to_state TEXT NOT NULL,
        duration_assigned REAL,
        vehicle_count_at_switch INTEGER,
        priority_score_at_switch REAL,
        FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
    )
    """)

    # Vehicle Detections Summary per session/class
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        vehicle_class TEXT NOT NULL,
        total_count INTEGER DEFAULT 0,
        FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
    )
    """)

    # System Logs / Events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        level TEXT DEFAULT 'INFO',
        category TEXT DEFAULT 'SYSTEM',
        message TEXT NOT NULL,
        details TEXT
    )
    """)

    conn.commit()
    conn.close()


def log_event(message: str, level: str = "INFO", category: str = "SYSTEM", details: Optional[str] = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO system_logs (timestamp, level, category, message, details) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), level, category, message, details)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB Log Error] {e}")


def get_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        logs = [dict(row) for row in rows]
        conn.close()
        return logs
    except Exception as e:
        print(f"[DB Get Logs Error] {e}")
        return []


def start_session(mode: str, source_name: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    name = f"{mode.capitalize()} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    cursor.execute(
        "INSERT INTO sessions (session_name, mode, source_name, started_at) VALUES (?, ?, ?, ?)",
        (name, mode, source_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    log_event(f"Session #{session_id} started ({mode}: {source_name})", "INFO", "SESSION")
    return session_id


def end_session(session_id: int, summary: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sessions SET
            ended_at = ?,
            total_vehicles = ?,
            total_cycles = ?,
            avg_waiting_time = ?,
            max_waiting_time = ?,
            avg_green_duration = ?
        WHERE id = ?
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        summary.get("total_vehicles", 0),
        summary.get("total_cycles", 0),
        summary.get("avg_waiting_time", 0.0),
        summary.get("max_waiting_time", 0.0),
        summary.get("avg_green_duration", 0.0),
        session_id
    ))
    conn.commit()
    conn.close()
    log_event(f"Session #{session_id} finished", "INFO", "SESSION")


def record_traffic_metric(session_id: int, metric_data: Dict[str, Any]):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO traffic_metrics (
                session_id, timestamp,
                north_count, south_count, east_count, west_count,
                north_density, south_density, east_density, west_density,
                north_wait, south_wait, east_wait, west_wait,
                current_green, green_duration, priority_scores
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            metric_data.get("north_count", 0),
            metric_data.get("south_count", 0),
            metric_data.get("east_count", 0),
            metric_data.get("west_count", 0),
            metric_data.get("north_density", "LOW"),
            metric_data.get("south_density", "LOW"),
            metric_data.get("east_density", "LOW"),
            metric_data.get("west_density", "LOW"),
            metric_data.get("north_wait", 0.0),
            metric_data.get("south_wait", 0.0),
            metric_data.get("east_wait", 0.0),
            metric_data.get("west_wait", 0.0),
            metric_data.get("current_green", "NORTH"),
            metric_data.get("green_duration", 10),
            json.dumps(metric_data.get("priority_scores", {}))
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB Record Metric Error] {e}")


def record_phase_switch(session_id: int, phase_data: Dict[str, Any]):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO signal_phases (
                session_id, timestamp, phase_direction, from_state, to_state,
                duration_assigned, vehicle_count_at_switch, priority_score_at_switch
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            phase_data.get("phase_direction", "NORTH"),
            phase_data.get("from_state", "RED"),
            phase_data.get("to_state", "GREEN"),
            phase_data.get("duration_assigned", 15.0),
            phase_data.get("vehicle_count", 0),
            phase_data.get("priority_score", 0.0)
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB Record Phase Error] {e}")
