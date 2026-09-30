from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/current")
async def get_current_sensors(db: Session = Depends(get_db)):
    # TODO: Get latest sensor readings
    return {
        "temperature": 28.5,
        "humidity": 65.0,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/history")
async def get_sensor_history(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    # TODO: Get sensor history from database
    return {
        "data": [],
        "from": (datetime.now() - timedelta(hours=hours)).isoformat(),
        "to": datetime.now().isoformat()
    }
