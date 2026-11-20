"""Face detection, alignment and embedding, shared by the backend and ai-models/face/.

Pipeline: YuNet finds the face and 5 landmarks -> alignCrop to a 112x112 canonical face ->
SFace gives a 128-d vector -> optional trained adapter (adapter.npz) -> cosine similarity.
The training scripts import this module so that training and serving preprocess identically.
Model files: run `python download_face_models.py` once.
"""
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

MODEL_DIR = Path(os.getenv("FACE_MODEL_DIR", Path(__file__).resolve().parent / "face_models"))
YUNET_FILE = "face_detection_yunet_2023mar.onnx"
SFACE_FILE = "face_recognition_sface_2021dec.onnx"
MODEL_TAG = "sface-2021dec"            # stored with every template: never compare across models
EMBED_DIM = 128

DETECT_SCORE = 0.6                     # YuNet confidence; masked faces score lower than bare ones
DETECT_MAX_SIDE = 640                  # detect on a downscaled copy, align on the original
# Quality gates for enrollment and data collection. Heuristics: tune on real webcam frames.
MIN_FACE_PX = 80
MIN_BRIGHTNESS = 40                    # mean gray level of the aligned face
MIN_SHARPNESS = 30.0                   # Laplacian variance of the eye region (mask-independent)

# Chosen by a leave-one-person-out test on the team's phone/webcam faces (HUONG_FACE_ID.md 4.4).
# OpenCV's LFW value 0.363 let a stranger in as a member in 19 of 30 attempts.
DEFAULT_THRESHOLDS = {"plain": 0.60, "mask": 0.65, "margin": 0.05}

# Mask polygon on the 112x112 aligned face. alignCrop maps eyes to y~52, nose tip to (56, 72)
# and mouth corners to y~92, so a fixed shape fits every face.
_MASK_POLYGON = np.array([(12, 67), (26, 61), (42, 58), (56, 57), (70, 58), (86, 61), (100, 67),
                          (102, 86), (94, 102), (78, 112), (34, 112), (18, 102), (10, 86)],
                         dtype=np.float32)
_MASK_COLORS = [(240, 240, 240), (225, 190, 140), (35, 35, 35), (160, 160, 160)]  # BGR


@dataclass
class Probe:
    """One image's usable face: its raw SFace vector, or the reason there is none."""
    vector: Optional[np.ndarray] = None
    reason: Optional[str] = None
    aligned: Optional[np.ndarray] = None


@dataclass
class Face:
    row: np.ndarray        # YuNet output row in original-image coordinates (15 values)

    @property
    def box(self):
        return self.row[:4]                     # x, y, w, h

    @property
    def landmarks(self):
        return self.row[4:14].reshape(5, 2)     # right eye, left eye, nose, mouth R, mouth L

    @property
    def score(self):
        return float(self.row[14])


class FaceEngine:
    def __init__(self, model_dir: Path = MODEL_DIR):
        model_dir = Path(model_dir)
        for name in (YUNET_FILE, SFACE_FILE):
            if not (model_dir / name).exists():
                raise FileNotFoundError(f"{model_dir / name} is missing: run download_face_models.py")
        self._detector = cv2.FaceDetectorYN.create(str(model_dir / YUNET_FILE), "", (320, 320),
                                                   DETECT_SCORE, 0.3, 5000)
        self._recognizer = cv2.FaceRecognizerSF.create(str(model_dir / SFACE_FILE), "")
        self._lock = threading.Lock()           # OpenCV DNN nets are not thread-safe
        self.adapter = load_adapter(model_dir / "adapter.npz")
        self.thresholds = load_thresholds(model_dir / "thresholds.json")

    def detect(self, img: np.ndarray) -> List[Face]:
        h, w = img.shape[:2]
        scale = min(1.0, DETECT_MAX_SIDE / max(h, w))
        small = cv2.resize(img, (round(w * scale), round(h * scale))) if scale < 1 else img
        with self._lock:
            self._detector.setInputSize((small.shape[1], small.shape[0]))
            _, rows = self._detector.detect(small)
        if rows is None:
            return []
        rows = rows.copy()
        rows[:, :14] /= scale
        return [Face(r) for r in rows]

    def align(self, img: np.ndarray, face: Face) -> np.ndarray:
        with self._lock:
            return self._recognizer.alignCrop(img, face.row.reshape(1, -1))

    def embed(self, aligned: np.ndarray) -> np.ndarray:
        """Raw SFace vector, L2-normalised, float32 (128,). Store this, not the adapted one."""
        with self._lock:
            f = self._recognizer.feature(aligned).reshape(-1).astype(np.float32)
        return f / np.linalg.norm(f)

    def adapt(self, x: np.ndarray) -> np.ndarray:
        return apply_adapter(self.adapter, x)

    def probe(self, img: np.ndarray, strict: bool = False) -> Probe:
        """Exactly one face -> its raw vector. strict adds the enrollment quality gates."""
        faces = self.detect(img)
        if not faces:
            return Probe(reason="Không thấy khuôn mặt")
        if len(faces) > 1:
            return Probe(reason="Có nhiều hơn một khuôn mặt")
        aligned = self.align(img, faces[0])
        reason = quality_reason(aligned, faces[0]) if strict else None
        if reason:
            return Probe(reason=reason)
        return Probe(self.embed(aligned), None, aligned)

    def masked_vectors(self, aligned: np.ndarray, n: int, rng: np.random.Generator) -> List[np.ndarray]:
        """Raw vectors of n synthetic-mask variants of an aligned face (for users without a real-mask enrollment)."""
        return [self.embed(synthetic_mask(aligned, rng)) for _ in range(n)]


def largest_face(faces: List[Face]) -> Optional[Face]:
    return max(faces, key=lambda f: f.box[2] * f.box[3]) if faces else None


def quality_reason(aligned: np.ndarray, face: Face) -> Optional[str]:
    """None if the face is good enough to enroll, otherwise the reason (shown to the user)."""
    if face.box[2] < MIN_FACE_PX:
        return "Mặt quá nhỏ, hãy lại gần camera hơn"
    gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
    if gray.mean() < MIN_BRIGHTNESS:
        return "Ảnh quá tối"
    if cv2.Laplacian(gray[20:62], cv2.CV_64F).var() < MIN_SHARPNESS:
        return "Ảnh bị mờ, hãy giữ yên"
    return None


def synthetic_mask(aligned: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Draw a random face mask over nose, cheeks, mouth and chin of an aligned 112x112 face."""
    pts = _MASK_POLYGON + rng.uniform(-3, 3, _MASK_POLYGON.shape)
    pts[:, 1] += rng.uniform(-2, 4)
    pts = np.round(pts).astype(np.int32)
    region = np.zeros(aligned.shape[:2], np.uint8)
    cv2.fillPoly(region, [pts], 255)

    color = np.array(_MASK_COLORS[rng.integers(len(_MASK_COLORS))], np.float32)
    color *= rng.uniform(0.85, 1.1)
    layer = np.empty(aligned.shape, np.float32)
    layer[:] = color
    if rng.random() < 0.6:                                  # pleats of a surgical mask
        for y in (74, 84, 94):
            y += int(rng.integers(-2, 3))
            cv2.line(layer, (0, y), (111, y), tuple(float(c) * 0.8 for c in color), 1)
    layer += rng.normal(0, 4, layer.shape)
    layer = cv2.GaussianBlur(layer, (3, 3), 0)

    out = aligned.copy()
    inside = region > 0
    out[inside] = np.clip(layer[inside], 0, 255).astype(np.uint8)
    return out


def load_adapter(path: Path) -> Optional[dict]:
    path = Path(path)
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k].astype(np.float32) for k in ("w1", "b1", "w2", "b2")}


def apply_adapter(params: Optional[dict], x: np.ndarray) -> np.ndarray:
    """y = normalize(x + W2 relu(W1 x + b1) + b2); identity when there is no trained adapter.
    Must match AdapterNet in ai-models/face/train_adapter.py."""
    x = np.asarray(x, np.float32)
    if params is None:
        return x
    h = np.maximum(x @ params["w1"].T + params["b1"], 0)
    y = x + h @ params["w2"].T + params["b2"]
    return y / np.linalg.norm(y, axis=-1, keepdims=True)


def match(probes: np.ndarray, users: np.ndarray, kinds: np.ndarray, templates: np.ndarray,
          thresholds: dict) -> dict:
    """Decide who is in front of the camera.

    probes: (frames, d) adapted login vectors; templates: (m, d) adapted enrolled vectors, owned by
    users[i] and of kind kinds[i]. score[u] = mean over frames of the best cosine against u's
    templates. The top user is accepted when the score reaches the threshold of the kind of their
    best-matching template ('plain', otherwise 'mask') and beats the runner-up by thresholds['margin'].
    reason: None, 'no_match' or 'ambiguous'.
    """
    sims = probes @ templates.T                                           # (frames, m)
    ids = np.unique(users)
    scores = np.stack([sims[:, users == u].max(axis=1) for u in ids], axis=1).mean(axis=0)
    order = np.argsort(-scores)
    best, score = ids[order[0]], float(scores[order[0]])
    second = float(scores[order[1]]) if len(ids) > 1 else -1.0
    own = users == best
    kind = str(kinds[own][int(np.argmax(sims[:, own].mean(axis=0)))])
    if score < thresholds["plain" if kind == "plain" else "mask"]:
        reason = "no_match"
    elif score - second < thresholds["margin"]:
        reason = "ambiguous"
    else:
        reason = None
    return {"user_id": int(best), "score": score, "second": second, "kind": kind, "reason": reason}


def load_thresholds(path: Path) -> dict:
    t = dict(DEFAULT_THRESHOLDS)
    path = Path(path)
    if path.exists():
        t.update({k: float(v) for k, v in json.loads(path.read_text()).items() if k in t})
    return t
