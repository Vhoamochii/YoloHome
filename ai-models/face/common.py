"""Paths, feature files, the LFW split and metrics shared by the face training scripts."""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))
import face_engine  # noqa: E402  (same preprocessing as the backend)

if hasattr(sys.stdout, "reconfigure"):           # Vietnamese text on a Windows pipe
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = HERE / "data"
TEAM_DIR = DATA / "team"                         # team/<person>/s<session>/<condition>/*.jpg
LFW_DIR = DATA / "lfw"
OUT = HERE / "out"
LFW_FEATURES = OUT / "features_lfw.npz"
TEAM_FEATURES = OUT / "features_team.npz"

CONDITIONS = ("plain", "mask", "mask_glasses")   # what collect.py records
MASKED = ("mask", "mask_glasses", "synthetic_mask")
SEED = 0
VAL_FRACTION = 0.2                               # share of LFW people held out for validation

FIELDS = ("person", "session", "condition", "image_id", "path")


def save_features(path: Path, emb: np.ndarray, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = {k: np.array([r[k] for r in rows]) for k in FIELDS}
    np.savez_compressed(path, emb=emb.astype(np.float32), **cols)


def load_features(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"{path} chưa có: chạy extract_features.py trước")
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def select(feats: dict, mask: np.ndarray) -> dict:
    return {k: v[mask] for k, v in feats.items()}


def lfw_val_people(people) -> set:
    """Deterministic person-level split: these LFW people are never used for training."""
    names = np.array(sorted(set(people)))
    rng = np.random.default_rng(SEED)
    return set(names[rng.permutation(len(names))[:round(len(names) * VAL_FRACTION)]])


def threshold_at_far(impostor, far=0.01):
    """Lowest threshold (accept if score >= threshold) whose FAR <= far."""
    q = np.quantile(np.asarray(impostor, np.float64), 1 - far, method="higher")
    return float(np.nextafter(q, np.inf))


def frr_at_far(genuine, impostor, far=0.01):
    """FRR at threshold_at_far. Genuine scores may be -inf (face missed or wrong person)."""
    thr = threshold_at_far(impostor, far)
    return float(np.mean(np.asarray(genuine, np.float64) < thr)), thr
