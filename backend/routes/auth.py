from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

class FaceLoginRequest(BaseModel):
    image: str  # Base64 encoded image

@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    # TODO: Implement login logic
    return {"token": "jwt_token_here", "user": {"id": 1, "email": request.email}}

@router.post("/face-login")
async def face_login(request: FaceLoginRequest, db: Session = Depends(get_db)):
    # TODO: Implement face recognition login
    return {"token": "jwt_token_here", "user": {"id": 1}}

@router.post("/register-face")
async def register_face(request: FaceLoginRequest, db: Session = Depends(get_db)):
    # TODO: Implement face registration
    return {"success": True, "message": "Face registered successfully"}
