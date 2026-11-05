from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from adafruit_mqtt import mqtt_client
from database import get_db
from models import Device, DeviceStatus

router = APIRouter()

# Default warning threshold
ALERT_TEMP_THRESHOLD = 35.0


class DeviceControlRequest(BaseModel):
    action: str  # 'on', 'off', 'set_speed', 'alert', 'safe'
    speed: Optional[int] = None


def ensure_default_devices(db: Session):
    """Seed initial smart devices if table is empty."""
    devices = db.query(Device).all()
    if not devices:
        fan = Device(
            name="Quạt thông minh (Fan)",
            type="fan",
            location="Phòng khách",
            adafruit_feed="yolohome-fan"
        )
        led = Device(
            name="Đèn LED cảnh báo (Alert LED)",
            type="led",
            location="Phòng khách",
            adafruit_feed="yolohome-led"
        )
        db.add_all([fan, led])
        db.commit()
        db.refresh(fan)
        db.refresh(led)

        status_fan = DeviceStatus(device_id=fan.id, status=False, speed=0, color=None)
        # LED initially in Safe/Normal mode (green/off)
        status_led = DeviceStatus(device_id=led.id, status=False, speed=0, color="00FF00")
        db.add_all([status_fan, status_led])
        db.commit()


@router.get("/")
async def get_devices(db: Session = Depends(get_db)):
    ensure_default_devices(db)
    devices = db.query(Device).all()

    result = []
    for d in devices:
        status_row = (
            db.query(DeviceStatus)
            .filter(DeviceStatus.device_id == d.id)
            .first()
        )
        # For LED: 'alert' status is True when color is FF0000 (red)
        is_alert = d.type == "led" and (status_row.status and status_row.color == "FF0000") if status_row else False

        result.append({
            "id": d.id,
            "name": d.name,
            "type": d.type,
            "location": d.location,
            "feed": d.adafruit_feed,
            "status": status_row.status if status_row else False,
            "speed": status_row.speed if status_row else 0,
            "color": status_row.color if status_row else None,
            "is_alert": is_alert,
            "updated_at": status_row.updated_at.isoformat() if status_row and status_row.updated_at else None
        })
    return result


@router.post("/{device_id}/control")
async def control_device(
    device_id: int,
    request: DeviceControlRequest,
    db: Session = Depends(get_db)
):
    ensure_default_devices(db)
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")

    status_row = db.query(DeviceStatus).filter(DeviceStatus.device_id == device.id).first()
    if not status_row:
        status_row = DeviceStatus(device_id=device.id, status=False, speed=0, color=None)
        db.add(status_row)

    cmd_value = "0"
    if device.type == "fan":
        if request.action == "on":
            status_row.status = True
            status_row.speed = status_row.speed if status_row.speed > 0 else 70
            cmd_value = str(status_row.speed)
        elif request.action == "off":
            status_row.status = False
            status_row.speed = 0
            cmd_value = "0"
        elif request.action == "set_speed" and request.speed is not None:
            clamped = max(0, min(100, request.speed))
            status_row.speed = clamped
            status_row.status = clamped > 0
            cmd_value = str(clamped)
        else:
            raise HTTPException(status_code=400, detail="Thao tác điều khiển quạt không hợp lệ")

    elif device.type == "led":
        # LED is strictly an alert/warning indicator
        if request.action in ("alert", "on"):
            # Trigger warning: Red alert
            status_row.status = True
            status_row.color = "FF0000"
            cmd_value = "FF0000"
        elif request.action in ("safe", "off"):
            # Normal / Safe state: Green or off
            status_row.status = False
            status_row.color = "00FF00"
            cmd_value = "OFF"
        else:
            raise HTTPException(status_code=400, detail="Thao tác cảnh báo đèn LED không hợp lệ")

    status_row.updated_at = datetime.utcnow()
    db.commit()

    # Dispatch to Adafruit IO MQTT
    mqtt_sent = False
    message = "Lưu trạng thái thành công"
    try:
        cmd_id = mqtt_client.send_command(device.type, cmd_value, actor="USER")
        mqtt_sent = cmd_id is not None
        if mqtt_sent:
            message = f"Đã gửi lệnh {device.name} -> Adafruit IO (ID: {cmd_id})"
        else:
            message = "Adafruit IO đang ngoại tuyến, đã lưu trạng thái cục bộ"
    except Exception as e:
        message = f"Lỗi MQTT: {str(e)}"

    return {
        "success": True,
        "device_id": device.id,
        "action": request.action,
        "feed": device.adafruit_feed,
        "value": cmd_value,
        "status": status_row.status,
        "speed": status_row.speed,
        "color": status_row.color,
        "is_alert": device.type == "led" and status_row.color == "FF0000" and status_row.status,
        "mqtt_sent": mqtt_sent,
        "message": message
    }
