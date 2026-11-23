import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import Counter
from pathlib import Path
from typing import List, Literal, Optional

import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

import face_engine
from database import get_db
from models import FaceTemplate, User

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

router = APIRouter()

FACE_KINDS = ("plain", "mask", "synthetic_mask")
MAX_TEMPLATES_PER_KIND = 20            # the oldest template of a kind is dropped beyond this
MAX_ENROLL_IMAGES = 12
MAX_LOGIN_IMAGES = 5
SYNTHETIC_PER_PLAIN = 2                # synthetic-mask templates generated from each plain face
MAX_IMAGE_CHARS = 4_000_000            # base64 of a ~3 MB photo; the app sends 640 px frames (~50 KB)
LOGIN_REJECTED = {
    "no_match": "Khuôn mặt không khớp với tài khoản nào.",
    "ambiguous": "Khuôn mặt giống nhiều tài khoản quá. Hãy tháo khẩu trang hoặc đăng nhập bằng mật khẩu.",
}

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
    if len(image_data) > MAX_IMAGE_CHARS:
        raise HTTPException(status_code=413, detail="Ảnh quá lớn.")
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


class FaceEnrollRequest(BaseModel):
    kind: Literal["plain", "mask"]
    images: List[str]  # base64 JPEG frames


class FaceLoginRequest(BaseModel):
    images: List[str]  # 2-5 webcam frames, ~300 ms apart


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

    has_face = db.query(FaceTemplate.id).filter(
        FaceTemplate.user_id == user.id, FaceTemplate.model == face_engine.MODEL_TAG
    ).first() is not None
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "has_face": has_face
    }


# ---------------------------------------------------------------------------
# Face ID: YuNet + SFace + trained adapter (face_engine.py, HUONG_FACE_ID.md)
# ---------------------------------------------------------------------------

_engine = None
_engine_lock = threading.Lock()


def get_face_engine():
    """Loads the ONNX models on first use, so the app starts (and tests run) without them."""
    global _engine
    with _engine_lock:
        if _engine is None:
            try:
                _engine = face_engine.FaceEngine(face_engine.MODEL_DIR)
            except FileNotFoundError:
                raise HTTPException(
                    status_code=503,
                    detail="Máy chủ chưa có model nhận diện khuôn mặt (chạy python download_face_models.py)."
                )
    return _engine


def require_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    user = get_current_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc phiên đã hết hạn.")
    return user


def face_counts(db: Session, user_id: int) -> dict:
    rows = (db.query(FaceTemplate.kind, func.count(FaceTemplate.id))
            .filter(FaceTemplate.user_id == user_id, FaceTemplate.model == face_engine.MODEL_TAG)
            .group_by(FaceTemplate.kind).all())
    counts = dict.fromkeys(FACE_KINDS, 0)
    counts.update({kind: n for kind, n in rows})
    return counts


def enroll_faces(db: Session, user: User, kind: str, images: List[str], engine) -> dict:
    """Store one template per usable image, plus synthetic-mask ones for plain faces, and keep the
    newest MAX_TEMPLATES_PER_KIND of each kind. 400 when no image is usable."""
    if not 1 <= len(images) <= MAX_ENROLL_IMAGES:
        raise HTTPException(status_code=400, detail=f"Cần từ 1 đến {MAX_ENROLL_IMAGES} ảnh.")
    rng = np.random.default_rng()
    rejected, new = [], []
    for index, data in enumerate(images):
        probe = engine.probe(decode_base64_image(data), strict=True)
        if probe.vector is None:
            rejected.append({"index": index, "reason": probe.reason})
            continue
        new.append((kind, probe.vector))
        if kind == "plain":
            new += [("synthetic_mask", v)
                    for v in engine.masked_vectors(probe.aligned, SYNTHETIC_PER_PLAIN, rng)]
    if not new:
        reason = Counter(r["reason"] for r in rejected).most_common(1)[0][0]
        raise HTTPException(status_code=400, detail=f"Không ảnh nào dùng được: {reason}.")

    db.add_all(FaceTemplate(user_id=user.id, kind=k, model=face_engine.MODEL_TAG,
                            embedding=np.asarray(v, np.float32).tobytes()) for k, v in new)
    db.flush()
    for k in FACE_KINDS:
        stale = (db.query(FaceTemplate)
                 .filter(FaceTemplate.user_id == user.id, FaceTemplate.kind == k)
                 .order_by(FaceTemplate.id.desc()).offset(MAX_TEMPLATES_PER_KIND).all())
        for template in stale:
            db.delete(template)
    db.commit()
    return {"accepted": len(images) - len(rejected), "rejected": rejected, "counts": face_counts(db, user.id)}


@router.post("/face/enroll")
def face_enroll(
    request: FaceEnrollRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    engine=Depends(get_face_engine)
):
    return enroll_faces(db, user, request.kind, request.images, engine)


@router.get("/face/status")
def face_status(user: User = Depends(require_user), db: Session = Depends(get_db)):
    counts = face_counts(db, user.id)
    return {"has_face": any(counts.values()), "counts": counts}


@router.delete("/face")
def face_delete(user: User = Depends(require_user), db: Session = Depends(get_db)):
    deleted = db.query(FaceTemplate).filter(FaceTemplate.user_id == user.id).delete()
    db.commit()
    return {"deleted": deleted}


@router.post("/face-login")
def face_login(request: FaceLoginRequest, db: Session = Depends(get_db), engine=Depends(get_face_engine)):
    """Match 2-5 webcam frames against every enrolled template; at least 2 must show one face."""
    images = request.images
    if not 2 <= len(images) <= MAX_LOGIN_IMAGES:
        raise HTTPException(status_code=400, detail=f"Cần từ 2 đến {MAX_LOGIN_IMAGES} ảnh.")
    rows = [t for t in db.query(FaceTemplate).filter(FaceTemplate.model == face_engine.MODEL_TAG).all()
            if len(t.embedding) == face_engine.EMBED_DIM * 4]
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Chưa có khuôn mặt nào được đăng ký. Hãy đăng nhập bằng mật khẩu rồi thiết lập Face ID."
        )

    probes = [engine.probe(decode_base64_image(data)) for data in images]
    vectors = [p.vector for p in probes if p.vector is not None]
    if len(vectors) < 2:
        reason = next(p.reason for p in probes if p.vector is None)
        raise HTTPException(status_code=400, detail=f"{reason}. Hãy nhìn thẳng vào camera và thử lại.")

    templates = np.stack([np.frombuffer(t.embedding, np.float32) for t in rows])
    result = face_engine.match(
        engine.adapt(np.stack(vectors)),
        np.array([t.user_id for t in rows]),
        np.array([t.kind for t in rows]),
        engine.adapt(templates),
        engine.thresholds,
    )
    if result["reason"]:
        raise HTTPException(status_code=401, detail=LOGIN_REJECTED[result["reason"]])

    user = db.query(User).filter(User.id == result["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin người dùng tương ứng.")
    return {
        "token": create_token(user.id),
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "score": round(result["score"], 3),
        "matched_kind": result["kind"],
    }
