import csv
import io
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from database import get_db
from models import SensorHistory, FireAlertHistory
from adafruit_mqtt import mqtt_client

router = APIRouter()


@router.get("/current")
async def get_current_sensors(db: Session = Depends(get_db)):
    latest = db.query(SensorHistory).order_by(SensorHistory.recorded_at.desc()).first()
    if latest:
        return {
            "temperature": latest.temperature,
            "humidity": latest.humidity,
            "timestamp": latest.recorded_at.isoformat() if latest.recorded_at else datetime.utcnow().isoformat()
        }
    return {
        "temperature": None,
        "humidity": None,
        "timestamp": None
    }


@router.get("/fire-status")
async def get_fire_status(db: Session = Depends(get_db)):
    """
    Get latest TinyML fire detection status from live MQTT stream or database.
    """
    state = mqtt_client.get_state()
    fire_alert = state.get("fire_alert")
    if fire_alert:
        return fire_alert

    latest = db.query(FireAlertHistory).order_by(FireAlertHistory.recorded_at.desc()).first()
    if latest:
        return {
            "state": latest.state,
            "score": latest.score,
            "is_alarm": (latest.state == "ALERT"),
            "updated_at": latest.recorded_at.isoformat() if latest.recorded_at else None
        }

    return {
        "state": "OK",
        "score": None,
        "is_alarm": False,
        "updated_at": None
    }


@router.get("/history")
async def get_sensor_history(
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(SensorHistory)
        .filter(SensorHistory.recorded_at >= since)
        .order_by(SensorHistory.recorded_at.asc())
        .all()
    )

    data = [
        {
            "id": r.id,
            "temperature": r.temperature,
            "humidity": r.humidity,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None
        }
        for r in rows
    ]

    return {
        "data": data,
        "from": since.isoformat(),
        "to": datetime.utcnow().isoformat()
    }


@router.get("/export-csv")
async def export_csv(
    hours: int = Query(168, ge=1, le=8760),
    db: Session = Depends(get_db)
):
    """
    Export sensor telemetry as a downloadable CSV file with UTF-8 BOM
    compatible with Microsoft Excel and Google Sheets.
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(SensorHistory)
        .filter(SensorHistory.recorded_at >= since)
        .order_by(SensorHistory.recorded_at.desc())
        .all()
    )

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["ID", "Thời gian ghi nhận", "Nhiệt độ (°C)", "Độ ẩm (%)"])

    for r in rows:
        t_val = f"{r.temperature:.1f}" if r.temperature is not None else ""
        h_val = f"{r.humidity:.1f}" if r.humidity is not None else ""
        time_str = r.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if r.recorded_at else ""
        writer.writerow([r.id, time_str, t_val, h_val])

    csv_data = output.getvalue()
    filename = f"yolohome_sensor_history_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
