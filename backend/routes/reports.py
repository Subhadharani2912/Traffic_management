import csv
import io
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import REPORTS_DIR, DB_PATH
from backend.database.database import get_db_connection, log_event
from backend.routes.analytics import get_analytics_summary, get_analytics_charts

router = APIRouter(prefix="/api/reports", tags=["Reports"])


class ReportRequest(BaseModel):
    format: str = "pdf"  # 'pdf' or 'csv'
    filter_period: str = "all"  # 'today', '7days', '30days', 'all'


def _collect_data(filter_period: str) -> Dict[str, Any]:
    summary = get_analytics_summary(filter_period)
    charts = get_analytics_charts(filter_period)
    return {"summary": summary, "charts": charts}


def _generate_pdf(data: Dict[str, Any], output_path: Path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas

    summary = data["summary"]
    charts = data["charts"]

    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    margin = 24 * mm
    y = height - margin

    c.setFillColor(colors.HexColor("#0a1b2b"))
    c.rect(0, height - 48 * mm, width, 48 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, height - 30 * mm, "AI Adaptive Traffic Management System")
    c.setFont("Helvetica", 11)
    c.drawString(margin, height - 42 * mm, "Automated Traffic Analytics Report")
    y = height - 52 * mm

    def heading(text):
        nonlocal y
        c.setFillColor(colors.HexColor("#0e3552"))
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin, y, text)
        y -= 8 * mm

    def row(label, value):
        nonlocal y
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 10)
        c.drawString(margin, y, label)
        c.drawRightString(width - margin, y, str(value))
        y -= 6 * mm

    def check_space(amount=25 * mm):
        nonlocal y
        if y < margin + amount:
            c.showPage()
            y = height - margin

    check_space()
    heading("Session Summary")
    row("Filter period", summary.get("filter", "all"))
    row("Total sessions", summary.get("total_sessions", 0))
    row("Total vehicles recorded", summary.get("total_vehicles_recorded", 0))
    row("Total signal cycles", summary.get("total_signal_cycles", 0))
    row("Average vehicles", summary.get("avg_vehicles_per_frame", 0))
    row("Peak vehicles detected", summary.get("peak_vehicles_detected", 0))
    row("Average waiting time (s)", summary.get("avg_waiting_time", 0))
    row("Max waiting time (s)", summary.get("max_waiting_time", 0))
    row("Average green duration (s)", summary.get("avg_green_duration", 0))
    row("Records collected", summary.get("records_count", 0))

    y -= 5 * mm
    check_space()
    heading("Volume by Direction")
    for item in charts.get("volume_by_direction", []):
        row(f"{item['direction']}", f"{item['count']} vehicles", )

    y -= 5 * mm
    check_space()
    heading("Average Waiting Time by Direction")
    for item in charts.get("waiting_by_direction", []):
        row(f"{item['direction']}", f"{item['avg_wait']} s")

    y -= 5 * mm
    check_space()
    heading("Signal Phase Usage")
    for item in charts.get("signal_usage", []):
        row(f"{item['direction']}", f"{item['count']} phases, avg {item['avg_duration']}s")

    y -= 5 * mm
    check_space()
    heading("Density Breakdown")
    for item in charts.get("density_breakdown", []):
        row(f"{item['level']}", f"{item['count']} samples")

    c.setFillColor(colors.grey)
    c.setFont("Helvetica", 8)
    c.drawString(margin, 15 * mm, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    c.save()


def _generate_csv(data: Dict[str, Any], output_path: Path):
    summary = data["summary"]
    charts = data["charts"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Session Summary"])
        for k, v in summary.items():
            writer.writerow([k, v])
        writer.writerow([])
        writer.writerow(["Volume by Direction"])
        writer.writerow(["direction", "count"])
        for item in charts.get("volume_by_direction", []):
            writer.writerow([item["direction"], item["count"]])
        writer.writerow([])
        writer.writerow(["Average Waiting Time by Direction"])
        writer.writerow(["direction", "avg_wait"])
        for item in charts.get("waiting_by_direction", []):
            writer.writerow([item["direction"], item["avg_wait"]])
        writer.writerow([])
        writer.writerow(["Signal Usage"])
        writer.writerow(["direction", "count", "avg_duration"])
        for item in charts.get("signal_usage", []):
            writer.writerow([item["direction"], item["count"], item["avg_duration"]])
        writer.writerow([])
        writer.writerow(["Density Breakdown"])
        writer.writerow(["level", "count"])
        for item in charts.get("density_breakdown", []):
            writer.writerow([item["level"], item["count"]])


@router.get("/list")
def list_reports():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(REPORTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in {".pdf", ".csv"}:
            files.append({
                "name": f.name,
                "type": f.suffix.lstrip("."),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "created": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    return {"reports": files}


@router.post("/generate")
def generate_report(req: ReportRequest):
    fmt = req.format.lower()
    if fmt not in {"pdf", "csv"}:
        raise HTTPException(status_code=400, detail="Format must be 'pdf' or 'csv'")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    data = _collect_data(req.filter_period)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"traffic_report_{req.filter_period}_{timestamp}.{fmt}"
    output = REPORTS_DIR / filename

    try:
        if fmt == "pdf":
            _generate_pdf(data, output)
        else:
            _generate_csv(data, output)
    except Exception as e:
        log_event(f"Report generation failed: {str(e)}", "ERROR", "REPORT")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

    log_event(f"Report generated: {filename}", "INFO", "REPORT")
    return {"status": "success", "filename": filename, "path": str(output)}


@router.get("/download/{filename}")
def download_report(filename: str):
    # Prevent path traversal
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = REPORTS_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")
    media_type = "application/pdf" if safe_name.endswith(".pdf") else "text/csv"
    return FileResponse(str(file_path), media_type=media_type, filename=safe_name)