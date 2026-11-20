"""Download the YuNet detector and SFace recognizer (OpenCV Zoo) into face_models/.

    python download_face_models.py
"""
import hashlib
import sys
import urllib.request

from face_engine import MODEL_DIR, SFACE_FILE, YUNET_FILE

ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"
MODELS = {
    YUNET_FILE: (f"{ZOO}/face_detection_yunet/{YUNET_FILE}",
                 "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    SFACE_FILE: (f"{ZOO}/face_recognition_sface/{SFACE_FILE}",
                 "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in MODELS.items():
        path = MODEL_DIR / name
        if path.exists() and sha256(path) == digest:
            print(f"ok       {name}")
            continue
        print(f"download {name}")
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        if sha256(tmp) != digest:
            tmp.unlink()
            sys.exit(f"{name}: checksum mismatch, file discarded")
        tmp.replace(path)
    print(f"models in {MODEL_DIR}")


if __name__ == "__main__":
    main()
