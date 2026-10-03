from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import sqlite3
import json
from backend.database.database import get_db_connection

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/summary")
def get_analytics_summary(filter_period: str = Query("all", description="today, 7days, 30days, all")):
    conn = get_db_connection()
    cursor = conn.cursor()

    time_filter = ""
    params = []
    if filter_period == "today":
        today_str = datetime.now().strftime("%Y-%m-%d")
        time_filter = "WHERE timestamp >= ?"
        params.append(f"{today_str} 00:00:00")
    elif filter_period == "7days":
        past_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        time_filter = "WHERE timestamp >= ?"
        params.append(past_str)
    elif filter_period == "30days":
        past_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        time_filter = "WHERE timestamp >= ?"
        params.append(past_str)

    cursor.execute(f"""
        SELECT
            COALESCE(MAX(north_count + south_count + east_count + west_count), 0) as peak_vehicles,
            COALESCE(AVG(north_count + south_count + east_count + west_count), 0) as avg_vehicles,
            COALESCE(AVG((north_wait + south_wait + east_wait + west_wait) / 4.0), 0) as avg_wait_time,
            COALESCE(MAX(MAX(north_wait, south_wait, east_wait, west_wait)), 0) as max_wait_time,
            COALESCE(AVG(green_duration), 15) as avg_green_duration,
            COUNT(*) as metric_records
        FROM traffic_metrics
        {time_filter}
    """, params)
    row = cursor.fetchone()

    # Total sessions
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_vehicles), 0), COALESCE(SUM(total_cycles), 0) FROM sessions")
    sess_row = cursor.fetchone()

    conn.close()

    return {
        "filter": filter_period,
        "total_sessions": sess_row[0] if sess_row else 0,
        "total_vehicles_recorded": sess_row[1] if sess_row else 0,
        "total_signal_cycles": sess_row[2] if sess_row else 0,
        "avg_vehicles_per_frame": round(float(row["avg_vehicles"]), 1) if row else 0.0,
        "peak_vehicles_detected": int(row["peak_vehicles"]) if row else 0,
        "avg_waiting_time": round(float(row["avg_wait_time"]), 1) if row else 0.0,
        "max_waiting_time": round(float(row["max_wait_time"]), 1) if row else 0.0,
        "avg_green_duration": round(float(row["avg_green_duration"]), 1) if row else 15.0,
        "records_count": row["metric_records"] if row else 0
    }


@router.get("/charts")
def get_analytics_charts(filter_period: str = Query("all")):
    conn = get_db_connection()
    cursor = conn.cursor()

    time_filter = ""
    params = []
    if filter_period == "today":
        today_str = datetime.now().strftime("%Y-%m-%d")
        time_filter = "WHERE timestamp >= ?"
        params.append(f"{today_str} 00:00:00")
    elif filter_period == "7days":
        past_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        time_filter = "WHERE timestamp >= ?"
        params.append(past_str)
    elif filter_period == "30days":
        past_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        time_filter = "WHERE timestamp >= ?"
        params.append(past_str)

    # 1. Time-series metrics (sampled up to 60 data points)
    cursor.execute(f"""
        SELECT
            timestamp,
            north_count, south_count, east_count, west_count,
            north_wait, south_wait, east_wait, west_wait,
            current_green, green_duration
        FROM traffic_metrics
        {time_filter}
        ORDER BY id DESC
        LIMIT 60
    """, params)
    raw_history = cursor.fetchall()
    history = [dict(r) for r in reversed(raw_history)]

    # 2. Cumulative volume by direction
    cursor.execute(f"""
        SELECT
            COALESCE(SUM(north_count), 0) as north,
            COALESCE(SUM(south_count), 0) as south,
            COALESCE(SUM(east_count), 0) as east,
            COALESCE(SUM(west_count), 0) as west
        FROM traffic_metrics
        {time_filter}
    """, params)
    dir_vols = cursor.fetchone()
    volume_by_direction = [
        {"direction": "NORTH", "count": dir_vols["north"] if dir_vols else 0},
        {"direction": "SOUTH", "count": dir_vols["south"] if dir_vols else 0},
        {"direction": "EAST",  "count": dir_vols["east"] if dir_vols else 0},
        {"direction": "WEST",  "count": dir_vols["west"] if dir_vols else 0},
    ]

    # 3. Average waiting time by direction
    cursor.execute(f"""
        SELECT
            COALESCE(AVG(north_wait), 0) as north,
            COALESCE(AVG(south_wait), 0) as south,
            COALESCE(AVG(east_wait), 0) as east,
            COALESCE(AVG(west_wait), 0) as west
        FROM traffic_metrics
        {time_filter}
    """, params)
    wait_avgs = cursor.fetchone()
    waiting_by_direction = [
        {"direction": "NORTH", "avg_wait": round(float(wait_avgs["north"]), 1) if wait_avgs else 0.0},
        {"direction": "SOUTH", "avg_wait": round(float(wait_avgs["south"]), 1) if wait_avgs else 0.0},
        {"direction": "EAST",  "avg_wait": round(float(wait_avgs["east"]), 1) if wait_avgs else 0.0},
        {"direction": "WEST",  "avg_wait": round(float(wait_avgs["west"]), 1) if wait_avgs else 0.0},
    ]

    # 4. Signal usage (green phase counts)
    cursor.execute(f"""
        SELECT
            current_green,
            COUNT(*) as count,
            COALESCE(AVG(green_duration), 15) as avg_duration
        FROM traffic_metrics
        {time_filter}
        GROUP BY current_green
    """, params)
    signal_rows = cursor.fetchall()
    signal_usage = [
        {"direction": r["current_green"], "count": r["count"], "avg_duration": round(float(r["avg_duration"]), 1)}
        for r in signal_rows if r["current_green"]
    ]

    # 5. Density breakdown
    cursor.execute(f"""
        SELECT
            north_density, COUNT(*) as cnt
        FROM traffic_metrics
        {time_filter}
        GROUP BY north_density
    """, params)
    density_breakdown = [{"level": r[0] or "LOW", "count": r[1]} for r in cursor.fetchall()]

    conn.close()

    return {
        "history": history,
        "volume_by_direction": volume_by_direction,
        "waiting_by_direction": waiting_by_direction,
        "signal_usage": signal_usage,
        "density_breakdown": density_breakdown
    }
