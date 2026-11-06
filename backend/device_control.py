"""Sends commands to the board and records what happened to them.

The board is the source of truth. A route never writes the fan state itself: the state changes
when the board reports it, so a refused or lost command cannot leave a wrong value in the DB.
"""
import logging
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from adafruit_mqtt import CommandError, mqtt_client
from database import SessionLocal
from models import ActivityLog, Device, DeviceStatus

log = logging.getLogger("device_control")

ALERT_COLOR = "FF0000"
DEFAULT_FAN_ON_SPEED = 70
ACTIONS = {"fan": ("on", "off", "set_speed", "auto"), "led": ("alert", "on", "safe", "off")}


def seed_default_devices():
    db = SessionLocal()
    try:
        if db.query(Device).first():
            return
        fan = Device(name="Quạt thông minh (Fan)", type="fan", location="Phòng khách",
                     adafruit_feed="yolohome-fan")
        led = Device(name="Đèn LED cảnh báo (Alert LED)", type="led", location="Phòng khách",
                     adafruit_feed="yolohome-led")
        db.add_all([fan, led])
        db.flush()
        db.add_all([DeviceStatus(device_id=fan.id, status=False, speed=0),
                    DeviceStatus(device_id=led.id, status=False, speed=0, color="00FF00")])
        db.commit()
    finally:
        db.close()


def command_value(device: Device, action: str, speed: Optional[int], current_speed: int) -> str:
    """Raises CommandError when the action makes no sense for this device."""
    if action not in ACTIONS.get(device.type, ()):
        raise CommandError(f"Thao tác '{action}' không hợp lệ cho thiết bị {device.type}")
    if device.type == "led":
        return ALERT_COLOR if action in ("alert", "on") else "OFF"
    if action == "on":
        return str(current_speed if current_speed > 0 else DEFAULT_FAN_ON_SPEED)
    if action == "off":
        return "0"
    if action == "auto":
        return "AUTO"
    if speed is None:
        raise CommandError("Thiếu tốc độ quạt")
    return str(max(0, min(100, speed)))


def dispatch(db: Session, device: Device, action: str, speed: Optional[int] = None,
             actor: str = "USER", hold_min: Optional[int] = None) -> dict:
    status = db.query(DeviceStatus).filter(DeviceStatus.device_id == device.id).first()
    value = command_value(device, action, speed, status.speed if status else 0)

    # Commit the log row BEFORE publishing: the ACK can arrive on the MQTT thread at any moment
    # after the publish and must find the row.
    cmd_id = secrets.token_hex(4)
    row = ActivityLog(cmd_id=cmd_id, device=device.type, action=f"{action} ({value})", actor=actor,
                      status="PENDING")
    db.add(row)
    db.commit()

    sent = False
    try:
        sent = mqtt_client.send_command(device.type, value, actor=actor, hold_min=hold_min,
                                        cmd_id=cmd_id) is not None
    finally:
        if not sent:
            row.status = "OFFLINE"
            db.commit()
    return {"cmd_id": cmd_id if sent else None, "value": value, "sent": sent}


# ---- handlers, called on the MQTT thread ------------------------------------------------------
def _on_ack(ack: dict):
    db = SessionLocal()
    try:
        status = "OK" if ack["ok"] else "REJECTED"
        row = None
        if ack["cmd_id"]:
            row = db.query(ActivityLog).filter(ActivityLog.cmd_id == ack["cmd_id"]).first()
        if row is None:                    # sent from the Adafruit dashboard
            row = ActivityLog(cmd_id=ack["cmd_id"], device=ack["device"], action=ack["value"],
                              actor=ack["actor"])
            db.add(row)
        row.status, row.reason, row.rtt_ms = status, ack["reason"], ack["rtt_ms"]
        if ack["ok"] and ack["device"] == "led":
            device = db.query(Device).filter(Device.type == "led").first()
            state = device and db.query(DeviceStatus).filter(DeviceStatus.device_id == device.id).first()
            if state:
                is_on = ack["value"].upper() != "000000"
                state.status = is_on
                state.color = ack["value"].upper() if is_on else "00FF00"
        db.commit()

        # If a scheduled fan command was refused because of a manual lockdown,
        # cancel the lockdown with AUTO and retry so the user's schedule actually takes effect:
        if (not ack["ok"] and ack.get("reason") == "LOCK" and ack.get("actor") == "SCHEDULE"
                and ack.get("device") == "fan"):
            log.warning("Fan schedule command was rejected due to board LOCK. Releasing lock and retrying...")
            try:
                mqtt_client.send_command("fan", "AUTO", actor="USER")
                mqtt_client.send_command("fan", ack["value"], actor="SCHEDULE", hold_min=30)
            except Exception as e:
                log.error("Failed to retry schedule after lock release: %s", e)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _on_timeout(cmd_id: str):
    db = SessionLocal()
    try:
        # Conditional: an ACK that got in first must not be overwritten.
        db.query(ActivityLog).filter(ActivityLog.cmd_id == cmd_id,
                                     ActivityLog.status == "PENDING").update({"status": "TIMEOUT"})
        db.commit()
    finally:
        db.close()


def _on_event(event: dict):
    db = SessionLocal()
    try:
        action = f"{event['type']}:{event['data']}" if event["data"] else event["type"]
        db.add(ActivityLog(device="board", action=action[:100], actor="BOARD", status="EVENT"))
        db.commit()
    finally:
        db.close()


_registered = False


def register_handlers():
    global _registered
    if not _registered:
        _registered = True
        mqtt_client.on("ack", _on_ack)
        mqtt_client.on("timeout", _on_timeout)
        mqtt_client.on("event", _on_event)
