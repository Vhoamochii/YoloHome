"""Ảnh → vector SFace (qua backend/face_engine.py), kèm khẩu trang giả lập.

    python extract_features.py lfw              # tải LFW (~180 MB) nếu chưa có, ~10 phút CPU
    python extract_features.py team             # ảnh nhóm trong data/team/

Kết quả: out/features_lfw.npz, out/features_team.npz.
Mỗi ảnh "plain" sinh thêm vài bản "synthetic_mask" cùng image_id (đã đổi sáng / lật ngẫu nhiên).
"""
import argparse
import hashlib
import tarfile
import urllib.request

import cv2
import numpy as np

from common import (LFW_DIR, LFW_FEATURES, SEED, TEAM_DIR, TEAM_FEATURES, face_engine,
                    save_features)

# Same archive and checksum as scikit-learn's fetch_lfw_people.
LFW_URL = "https://ndownloader.figshare.com/files/5976018"
LFW_SHA256 = "055f7d9c632d7370e6fb4afc7468d40f970c34a80d4c6f50ffec63f5a8d536c0"


def jitter(aligned, rng):
    out = aligned.astype(np.float32) * rng.uniform(0.7, 1.2) + rng.uniform(-15, 15)
    out = np.clip(out, 0, 255).astype(np.uint8)
    return out[:, ::-1].copy() if rng.random() < 0.5 else out


class Extractor:
    def __init__(self, masks):
        self.engine = face_engine.FaceEngine()
        self.rng = np.random.default_rng(SEED)
        self.masks = masks
        self.emb, self.rows = [], []
        self.next_id = 0

    def add(self, img, face, person, session, condition, path):
        aligned = self.engine.align(img, face)
        image_id, self.next_id = self.next_id, self.next_id + 1
        self._put(self.engine.embed(aligned), person, session, condition, image_id, path)
        if condition == "plain":
            for _ in range(self.masks):
                masked = face_engine.synthetic_mask(jitter(aligned, self.rng), self.rng)
                self._put(self.engine.embed(masked), person, session, "synthetic_mask", image_id, path)

    def _put(self, vec, person, session, condition, image_id, path):
        self.emb.append(vec)
        self.rows.append(dict(person=person, session=session, condition=condition,
                              image_id=image_id, path=path))

    def save(self, path):
        save_features(path, np.stack(self.emb), self.rows)
        n_img = len({r["image_id"] for r in self.rows})
        print(f"{n_img} ảnh → {len(self.rows)} vector, {len({r['person'] for r in self.rows})} người → {path}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lfw_archive():
    path = LFW_DIR / "lfw.tgz"
    if not path.exists():
        LFW_DIR.mkdir(parents=True, exist_ok=True)
        print("Tải LFW (~180 MB)...")
        urllib.request.urlretrieve(LFW_URL, path.with_suffix(".part"))
        path.with_suffix(".part").replace(path)
    if sha256(path) != LFW_SHA256:
        raise SystemExit(f"{path}: sai checksum, xoá file rồi chạy lại")
    return path


def central_face(faces, img):
    """LFW centres the labelled person; other faces are bystanders."""
    cy, cx = img.shape[0] / 2, img.shape[1] / 2
    return min(faces, key=lambda f: (f.box[0] + f.box[2] / 2 - cx) ** 2 + (f.box[1] + f.box[3] / 2 - cy) ** 2)


def extract_lfw(masks, limit):
    ex, seen, skipped = Extractor(masks), 0, 0
    with tarfile.open(lfw_archive(), "r:gz") as tar:      # streamed, never unpacked to disk
        for member in tar:
            if not (member.isfile() and member.name.endswith(".jpg")):
                continue
            img = cv2.imdecode(np.frombuffer(tar.extractfile(member).read(), np.uint8), cv2.IMREAD_COLOR)
            faces = ex.engine.detect(img)
            if not faces:
                skipped += 1
                continue
            ex.add(img, central_face(faces, img), member.name.split("/")[-2], 0, "plain", member.name)
            seen += 1
            if seen % 1000 == 0:
                print(f"  {seen} ảnh...")
            if limit and seen >= limit:
                break
    print(f"Bỏ qua {skipped} ảnh không tìm thấy mặt")
    ex.save(LFW_FEATURES)


def extract_team(masks):
    ex, skipped = Extractor(masks), []
    files = sorted(TEAM_DIR.glob("*/s*/*/*.jpg"))
    if not files:
        raise SystemExit(f"Chưa có ảnh trong {TEAM_DIR}: chạy collect.py trước")
    for f in files:
        person, session, condition = f.parts[-4], int(f.parts[-3][1:]), f.parts[-2]
        img = cv2.imread(str(f))
        face = face_engine.largest_face(ex.engine.detect(img)) if img is not None else None
        if face is None:
            skipped.append(f)
            continue
        ex.add(img, face, person, session, condition, f.relative_to(TEAM_DIR).as_posix())
    if skipped:
        print(f"Bỏ qua {len(skipped)} ảnh không tìm thấy mặt, ví dụ {skipped[0]}")
    ex.save(TEAM_FEATURES)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", choices=("lfw", "team"))
    p.add_argument("--masks", type=int, help="số khẩu trang giả mỗi ảnh plain (mặc định lfw 2, team 1)")
    p.add_argument("--limit", type=int, default=0, help="lfw: chỉ lấy N ảnh đầu (chạy thử)")
    a = p.parse_args()
    if a.source == "lfw":
        extract_lfw(2 if a.masks is None else a.masks, a.limit)
    else:
        extract_team(1 if a.masks is None else a.masks)


if __name__ == "__main__":
    main()
