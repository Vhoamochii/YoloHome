from datetime import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from device_control import ACTIONS
from models import Device, Schedule
from timeutil import iso_utc

router = APIRouter()


class ScheduleCreateRequest(BaseModel):
    device_id: int
    action: str  # 'on', 'off', 'set_speed', 'alert'
    scheduled_time: str  # "07:30" or "07:30:00"
    repeat_mode: str = "daily"  # 'once', 'daily', 'weekly'
    is_active: bool = True
    speed: Optional[int] = None  # required for 'set_speed'


class ScheduleUpdateRequest(BaseModel):
    device_id: Optional[int] = None
    action: Optional[str] = None
    scheduled_time: Optional[str] = None
    repeat_mode: Optional[str] = None
    is_active: Optional[bool] = None
    speed: Optional[int] = None


def parse_time_str(val: str) -> time:
    try:
        val = val.strip()
        if len(val) == 5:
            return time.fromisoformat(f"{val}:00")
        return time.fromisoformat(val)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng giờ '{val}' không hợp lệ. Vui lòng dùng định dạng HH:MM (ví dụ 07:30)."
        )


def validate_schedule(device: Device, action: str, repeat_mode: str, speed: Optional[int]):
    if action == "auto" or action not in ACTIONS.get(device.type, ()):
        raise HTTPException(status_code=400, detail=f"Hành động '{action}' không hợp lệ cho thiết bị này.")
    if repeat_mode not in ("once", "daily", "weekly"):
        raise HTTPException(status_code=400, detail=f"Chế độ lặp '{repeat_mode}' không hợp lệ.")
    if action == "set_speed" and (speed is None or not 0 <= speed <= 100):
        raise HTTPException(status_code=400, detail="Tốc độ quạt phải từ 0 đến 100.")


def format_schedule_response(s: Schedule, db: Session):
    device = db.query(Device).filter(Device.id == s.device_id).first()
    time_str = ""
    if s.scheduled_time:
        if isinstance(s.scheduled_time, time):
            time_str = s.scheduled_time.strftime("%H:%M")
        else:
            time_str = str(s.scheduled_time)[:5]

    return {
        "id": s.id,
        "device_id": s.device_id,
        "device_name": device.name if device else "Thiết bị",
        "action": s.action,
        "scheduled_time": time_str,
        "repeat_mode": s.repeat_mode,
        "is_active": s.is_active,
        "speed": s.speed,
        "created_at": iso_utc(s.created_at)
    }


@router.get("/")
def list_schedules(db: Session = Depends(get_db)):
    rows = db.query(Schedule).order_by(Schedule.id.asc()).all()
    return [format_schedule_response(r, db) for r in rows]


@router.post("/")
def create_schedule(
    request: ScheduleCreateRequest,
    db: Session = Depends(get_db)
):
    device = db.query(Device).filter(Device.id == request.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị để lập lịch.")

    validate_schedule(device, request.action, request.repeat_mode, request.speed)
    t_val = parse_time_str(request.scheduled_time)
    speed_val = request.speed
    if request.action == "on" and speed_val is None:
        speed_val = 70
    schedule = Schedule(
        device_id=request.device_id,
        action=request.action,
        scheduled_time=t_val,
        repeat_mode=request.repeat_mode,
        is_active=request.is_active,
        speed=speed_val
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    return format_schedule_response(schedule, db)


@router.patch("/{schedule_id}")
def update_schedule(
    schedule_id: int,
    request: ScheduleUpdateRequest,
    db: Session = Depends(get_db)
):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch trình.")

    if request.device_id is not None:
        device = db.query(Device).filter(Device.id == request.device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị.")
        schedule.device_id = request.device_id

    if request.action is not None:
        schedule.action = request.action
        if schedule.action == "on" and schedule.speed is None:
            schedule.speed = 70

    if request.scheduled_time is not None:
        schedule.scheduled_time = parse_time_str(request.scheduled_time)

    if request.repeat_mode is not None:
        schedule.repeat_mode = request.repeat_mode

    if request.is_active is not None:
        schedule.is_active = request.is_active

    if request.speed is not None:
        schedule.speed = request.speed

    device = db.query(Device).filter(Device.id == schedule.device_id).first()
    validate_schedule(device, schedule.action, schedule.repeat_mode, schedule.speed)

    db.commit()
    db.refresh(schedule)
    return format_schedule_response(schedule, db)


@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db)
):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch trình.")

    db.delete(schedule)
    db.commit()
    return {"success": True, "message": "Đã xóa lịch trình thành công."}

