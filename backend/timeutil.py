"""The database stores naive UTC; the API sends explicit UTC; schedules and CSV use local time."""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

LOCAL_OFFSET = timedelta(hours=float(os.getenv("APP_UTC_OFFSET_HOURS", "7")))  # like TZ_OFFSET_S


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value: Optional[datetime]) -> Optional[str]:
    """Without the Z, browsers read the value as local time and show it 7 hours off."""
    return value.isoformat() + "Z" if value else None


def to_local(value: datetime) -> datetime:
    return value + LOCAL_OFFSET


def local_now() -> datetime:
    return to_local(utcnow())
