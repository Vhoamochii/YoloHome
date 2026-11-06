import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import FaceProfile, User
try:
    import face_recognition
    HAS_FACE_RECOGNITION = True
except Exception:
    HAS_FACE_RECOGNITION = False

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "yolohome-super-secret-key-2026")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}:{key.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        if ":" not in hashed:
            return password == hashed
        salt, key_hex = hashed.split(":", 1)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


def create_token(user_id: int) -> str:
    exp = int(time.time()) + 86400 * 7
    payload = f"{user_id}:{exp}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def get_user_id_from_token(token: str) -> Optional[int]:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        parts = raw.split(":")
        if len(parts) != 3:
            return None
        user_id_str, exp_str, sig = parts
        payload = f"{user_id_str}:{exp_str}"
        expected_sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        if int(exp_str) < time.time():
            return None
        return int(user_id_str)
    except Exception:
        return None


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    user_id = get_user_id_from_token(token)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def decode_base64_image(image_data: str) -> np.ndarray:
    try:
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        img_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Không thể giải mã dữ liệu hình ảnh.")
        return img
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dữ liệu ảnh không hợp lệ: {str(e)}"
        )


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class FaceLoginRequest(BaseModel):
    image: str  # Base64 encoded image string


class RegisterFaceRequest(BaseModel):
    image: str
    email: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth Endpoints
# ---------------------------------------------------------------------------

@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Email không hợp lệ.")
    if len(request.password) < 4:
        raise HTTPException(status_code=400, detail="Mật khẩu phải có ít nhất 4 ký tự.")

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký.")

    hashed = hash_password(request.password)
    user = User(
        email=email,
        password=hashed,
        name=request.name.strip() if request.name else email.split("@")[0]
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name
        }
    }


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không chính xác.")

    token = create_token(user.id)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name
        }
    }


@router.get("/me")
def me(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc phiên đã hết hạn.")

    has_face = db.query(FaceProfile).filter(FaceProfile.user_id == user.id).first() is not None
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "has_face": has_face
    }


# ---------------------------------------------------------------------------
# Face Recognition Endpoints (Registration & Login)
# ---------------------------------------------------------------------------

@router.post("/register-face")
def register_face(
    request: RegisterFaceRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Extracts face embedding from base64 image and saves to face_profiles in database.
    Can be called by an authenticated user OR by specifying user email.
    """
    if not HAS_FACE_RECOGNITION:
        raise HTTPException(
            status_code=500,
            detail="Thư viện nhận diện khuôn mặt chưa sẵn sàng trên máy chủ."
        )

    # Resolve target user
    user = get_current_user(authorization, db)
    if not user and request.email:
        email = request.email.strip().lower()
        user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Vui lòng đăng nhập hoặc cung cấp email tài khoản cần đăng ký khuôn mặt."
        )

    # Decode and process image
    img_bgr = decode_base64_image(request.image)
    rgb_image = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    encodings = face_recognition.face_encodings(rgb_image)
    if not encodings:
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy khuôn mặt trong ảnh! Vui lòng nhìn thẳng vào camera ở nơi đủ ánh sáng."
        )

    # 128-dimensional float64 vector
    face_encoding = encodings[0]
    encoding_bytes = face_encoding.tobytes()

    # Update or create FaceProfile in database
    profile = db.query(FaceProfile).filter(FaceProfile.user_id == user.id).first()
    if profile:
        profile.face_encoding = encoding_bytes
    else:
        profile = FaceProfile(user_id=user.id, face_encoding=encoding_bytes)
        db.add(profile)

    db.commit()
    return {
        "success": True,
        "message": f"Đã lưu khuôn mặt thành công cho tài khoản {user.email}!",
        "user_id": user.id
    }


@router.post("/face-login")
def face_login(request: FaceLoginRequest, db: Session = Depends(get_db)):
    """
    Recognizes face from camera capture, matches with profiles stored in database,
    and returns JWT token for authenticated user.
    """
    if not HAS_FACE_RECOGNITION:
        raise HTTPException(
            status_code=500,
            detail="Thư viện nhận diện khuôn mặt chưa sẵn sàng trên máy chủ."
        )

    # 1. Decode captured image
    img_bgr = decode_base64_image(request.image)
    rgb_image = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    encodings = face_recognition.face_encodings(rgb_image)
    if not encodings:
        raise HTTPException(
            status_code=400,
            detail="Không phát hiện khuôn mặt trong khung hình. Vui lòng thử lại!"
        )

    probe_encoding = encodings[0]

    # 2. Query all registered face profiles from database
    profiles = db.query(FaceProfile).all()
    if not profiles:
        raise HTTPException(
            status_code=404,
            detail="Chưa có khuôn mặt nào được đăng ký trong hệ thống. Vui lòng đăng nhập bằng mật khẩu trước để đăng ký khuôn mặt!"
        )

    known_encodings = []
    user_ids = []
    for p in profiles:
        if p.face_encoding and len(p.face_encoding) == 128 * 8:
            arr = np.frombuffer(p.face_encoding, dtype=np.float64)
            known_encodings.append(arr)
            user_ids.append(p.user_id)

    if not known_encodings:
        raise HTTPException(
            status_code=404,
            detail="Không có hồ sơ khuôn mặt hợp lệ trong hệ thống."
        )

    # 3. Calculate Euclidean distance between probe face and database faces
    distances = face_recognition.face_distance(known_encodings, probe_encoding)
    best_match_index = int(np.argmin(distances))
    best_distance = float(distances[best_match_index])

    # Standard threshold for face_recognition (default is 0.6; 0.55 is strict & safe)
    MATCH_THRESHOLD = 0.55

    if best_distance > MATCH_THRESHOLD:
        raise HTTPException(
            status_code=401,
            detail=f"Khuôn mặt không khớp với bất kỳ tài khoản nào (khoảng cách sai lệch: {best_distance:.2f})."
        )

    matched_user_id = user_ids[best_match_index]
    user = db.query(User).filter(User.id == matched_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin người dùng tương ứng.")

    token = create_token(user.id)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name
        },
        "distance": best_distance
    }
