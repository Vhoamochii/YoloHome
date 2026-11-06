from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from adafruit_mqtt import CommandError, mqtt_client
from database import get_db
from device_control import ALERT_COLOR, dispatch
from models import Device, DeviceStatus
from timeutil import iso_utc

router = APIRouter()


class DeviceControlRequest(BaseModel):
    action: str  # fan: on, off, set_speed, auto; led: alert, safe
    speed: Optional[int] = None
    actor: Optional[str] = "USER"


def alert_level(device: Device, status: Optional[DeviceStatus], state: dict) -> Optional[str]:
    """What the board's LEDs are showing: SAFETY (red), HOT (orange) or a manual TEST (red)."""
    if device.type != "led":
        return None
    if state.get("safety"):
        return "SAFETY"
    if state.get("hot"):
        return "HOT"
    if status and status.status and status.color == ALERT_COLOR:
        return "TEST"
    return None


@router.get("/")
def get_devices(db: Session = Depends(get_db)):
    # Read-only: writing a cached value here used to overwrite newer state from other threads.
    state = mqtt_client.get_state()
    result = []
    for d in db.query(Device).all():
        status = db.query(DeviceStatus).filter(DeviceStatus.device_id == d.id).first()
        level = alert_level(d, status, state)
        result.append({
            "id": d.id,
            "name": d.name,
            "type": d.type,
            "location": d.location,
            "feed": d.adafruit_feed,
            "status": status.status if status else False,
            "speed": status.speed if status else 0,
            "color": status.color if status else None,
            "alert_level": level,
            "is_alert": level is not None,
            "mode": state.get("mode") or "AUTO_AI",
            "updated_at": iso_utc(status.updated_at) if status else None
        })
    return result


@router.post("/{device_id}/control")
def control_device(device_id: int, request: DeviceControlRequest, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")
    actor = (request.actor or "USER").upper()
    if actor not in ("USER", "VOICE"):
        actor = "USER"
    try:
        result = dispatch(db, device, request.action, request.speed, actor=actor)
    except CommandError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": result["sent"],
        "device_id": device.id,
        "action": request.action,
        "feed": device.adafruit_feed,
        "value": result["value"],
        "cmd_id": result["cmd_id"],
        "mqtt_sent": result["sent"],
        "message": (f"Đã gửi lệnh tới {device.name}, đang chờ mạch xác nhận..." if result["sent"]
                    else "Adafruit IO đang ngoại tuyến, lệnh chưa được gửi.")
    }
