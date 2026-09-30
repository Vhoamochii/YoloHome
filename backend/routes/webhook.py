from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from database import get_db

router = APIRouter()

@router.post("/adafruit")
async def handle_adafruit_webhook(request: Request, db: Session = Depends(get_db)):
    # TODO: Handle Adafruit IO webhook
    data = await request.json()
    return {"success": True, "received": data}
