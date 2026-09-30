from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from adafruit_mqtt import mqtt_client
from typing import List, Optional

router = APIRouter()

class DeviceControlRequest(BaseModel):
    action: str  # 'on', 'off', 'set_speed', 'set_color'
    speed: Optional[int] = None
    color: Optional[str] = None

@router.get("/")
async def get_devices(db: Session = Depends(get_db)):
    # TODO: Get all devices from database
    return [
        {"id": 1, "name": "Living Room Fan", "type": "fan", "status": False, "feed": "yolohome-fan"},
        {"id": 2, "name": "LED Strip", "type": "led", "status": True, "feed": "yolohome-led"}
    ]

@router.post("/{device_id}/control")
async def control_device(device_id: int, request: DeviceControlRequest, db: Session = Depends(get_db)):
    """
    Control device via Adafruit IO MQTT
    This sends commands to ESP32 through Adafruit IO
    """
    
    # Map device_id to feed name
    device_feeds = {
        1: "yolohome-fan",
        2: "yolohome-led"
    }
    
    if device_id not in device_feeds:
        raise HTTPException(status_code=404, detail="Device not found")
    
    feed = device_feeds[device_id]
    
    # Prepare command based on action
    if request.action == "on":
        value = "1"
    elif request.action == "off":
        value = "0"
    elif request.action == "set_speed" and request.speed is not None:
        value = str(request.speed)  # 0-100
    elif request.action == "set_color" and request.color is not None:
        value = request.color  # RGB hex like "FF0000"
    else:
        raise HTTPException(status_code=400, detail="Invalid action or missing parameters")
    
    # Publish to Adafruit IO (which ESP32 is subscribed to)
    success = mqtt_client.publish(feed, value)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send command to Adafruit IO")
    
    # TODO: Update device status in database
    
    return {
        "success": True,
        "device_id": device_id,
        "action": request.action,
        "feed": feed,
        "value": value,
        "message": f"Command sent to {feed}"
    }
