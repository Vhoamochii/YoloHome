from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import ActivityLog
from timeutil import iso_utc

router = APIRouter()


@router.get("/")
def list_activity(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    rows = db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(limit).all()
    return [{
        "id": r.id,
        "cmd_id": r.cmd_id,
        "device": r.device,
        "action": r.action,
        "actor": r.actor,
        "status": r.status,
        "reason": r.reason,
        "rtt_ms": r.rtt_ms,
        "created_at": iso_utc(r.created_at),
    } for r in rows]
