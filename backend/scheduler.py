"""Runs the schedules in lich_trinh. Schedule times are local time (see timeutil)."""
import logging
import threading
from datetime import datetime, time, timedelta
from typing import Optional

from sqlalchemy import or_

from adafruit_mqtt import mqtt_client
from database import SessionLocal
from device_control import dispatch
from models import Device, Schedule
from timeutil import local_now, to_local

log = logging.getLogger("scheduler")

TICK_S = 15
GRACE = timedelta(minutes=2)   # missed by longer (server was down): skip, don't run late
SCHEDULE_HOLD_MIN = 30         # keeps the board's AI from overriding the schedule immediately


def due_at(schedule: Schedule, now: datetime) -> Optional[datetime]:
    """The moment this schedule is due, if that is now; None otherwise."""
    if not schedule.is_active or schedule.scheduled_time is None:
        return None
    sched_time = schedule.scheduled_time
    if isinstance(sched_time, str):
        try:
            sched_time = time.fromisoformat(sched_time[:8])
        except Exception:
            return None
    due = datetime.combine(now.date(), sched_time)
    if not due <= now < due + GRACE:
        return None
    created = schedule.created_at
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created)
        except Exception:
            created = None
    if schedule.repeat_mode == "weekly" and created is not None \
            and to_local(created).weekday() != now.weekday():
        return None
    last_run = schedule.last_run_at
    if isinstance(last_run, str):
        try:
            last_run = datetime.fromisoformat(last_run)
        except Exception:
            last_run = None
    if last_run is not None and last_run >= due:
        return None
    return due


def run_due(now: Optional[datetime] = None) -> int:
    """Returns how many schedules fired."""
    now = now or local_now()
    fired = 0
    db = SessionLocal()
    try:
        for schedule in db.query(Schedule).filter(Schedule.is_active.is_(True)).all():
            due = due_at(schedule, now)
            if due is None:
                continue
            # Atomic claim: if two processes tick together (uvicorn reload, several workers)
            # only one UPDATE matches, so the command goes out once.
            values = {"last_run_at": now}
            if schedule.repeat_mode == "once":
                values["is_active"] = False
            claimed = db.query(Schedule).filter(
                Schedule.id == schedule.id,
                or_(Schedule.last_run_at.is_(None), Schedule.last_run_at < due),
            ).update(values, synchronize_session=False)
            db.commit()
            if not claimed:
                continue
            fired += 1
            device = db.query(Device).filter(Device.id == schedule.device_id).first()
            if device is None:
                continue
            try:
                state = mqtt_client.get_state()
                mode = state.get("mode") or ""
                if "MANUAL" in mode and device.type == "fan":
                    try:
                        mqtt_client.send_command("fan", "AUTO", actor="USER")
                    except Exception:
                        pass
                hold = SCHEDULE_HOLD_MIN if device.type == "fan" else None
                dispatch(db, device, schedule.action, schedule.speed, actor="SCHEDULE", hold_min=hold)
            except ValueError as e:
                log.error("schedule %s is invalid: %s", schedule.id, e)
    finally:
        db.close()
    return fired


class Scheduler:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="scheduler", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            try:
                run_due()
                mqtt_client.expire_pending()
            except Exception:          # one bad tick must not end the scheduler
                log.exception("scheduler tick failed")
            self._stop.wait(TICK_S)


scheduler = Scheduler()
