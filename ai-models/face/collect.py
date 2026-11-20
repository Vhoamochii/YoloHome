"""Thu ảnh khuôn mặt cho bộ dữ liệu của nhóm: từ video/ảnh thành viên gửi, hoặc webcam máy này.

Video và ảnh chụp bằng điện thoại: xếp vào data/raw/<người>/<điều kiện>/ rồi chạy một lệnh.
Điều kiện: plain (không đeo gì), mask (khẩu trang), mask_glasses (khẩu trang + kính).
    data/raw/an/plain/video.mp4
    data/raw/an/mask/IMG_0012.jpg
    python collect.py --import

Webcam máy này:
    python collect.py --person an --condition plain
    python collect.py --person an --condition mask_glasses --seconds 15

Chỉ lưu khung có đúng một khuôn mặt đủ rõ. Video lấy khung cách nhau --interval giây; video/ảnh bị
nằm ngang hoặc ngược được tự xoay lại. Ảnh lưu ở data/team/<người>/s1/<điều kiện>/ (không commit).
Chạy lại --import không tạo ảnh trùng: thêm file vào data/raw rồi chạy lại là đủ.
Cuối mỗi lần chạy in số ảnh của từng người, tính cả ảnh từ video, ảnh chụp và webcam.
"""
import argparse
import os
import re
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from common import CONDITIONS, DATA, TEAM_DIR, face_engine

RAW_DIR = DATA / "raw"
GREEN, RED = (0, 200, 0), (0, 0, 230)
SAVE_MAX_SIDE = 1280                     # phone videos are 1080p-4K; this is plenty for alignment
MIN_IMAGES = 50
NAME = re.compile(r"[a-z0-9_-]+")
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".3gp", ".webm"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
IGNORED = {"thumbs.db", "desktop.ini", ".ds_store"}
ROTATIONS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
IPHONE_HINT = ("File iPhone (HEVC/HEIC): gửi qua Zalo/Messenger để được đổi sang mp4/jpg, "
               "hoặc chọn Cài đặt > Camera > Định dạng > Tương thích nhất.")


def judge(engine, frame):
    """('ok', face, None) if the frame can be saved, else (short status, face or None, reason)."""
    faces = engine.detect(frame)
    if not faces:
        return "no face", None, "Không thấy khuôn mặt"
    if len(faces) > 1:
        return "2+ faces", None, "Có nhiều hơn một khuôn mặt"
    face = faces[0]
    reason = face_engine.quality_reason(engine.align(frame, face), face)
    return ("low quality" if reason else "ok"), face, reason


def rotate(frame, angle):
    return cv2.rotate(frame, ROTATIONS[angle]) if angle else frame


def upright_angle(engine, frames):
    """The rotation with the most confident detections. YuNet also finds sideways and upside-down
    faces, just with a lower score, so 'any face found' is not enough. Ties (no face at all) give 0."""
    def confidence(angle):
        return sum(max((f.score for f in engine.detect(rotate(fr, angle))), default=0.0) for fr in frames)
    return max((0, 90, 270, 180), key=confidence)


def safe_stem(path):
    return re.sub(r"[^A-Za-z0-9_-]", "_", path.stem)


def save(path, frame):
    h, w = frame.shape[:2]
    scale = SAVE_MAX_SIDE / max(h, w)
    if scale < 1:
        frame = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])


def skipped_text(skipped):
    detail = ", ".join(f"{r}: {n}" for r, n in skipped.most_common())
    return f" (bỏ qua {detail})" if detail else ""


def open_video(path):
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)       # honour the phone's portrait/landscape flag
    return cap


def from_video(engine, path, out, interval):
    cap = open_video(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    samples = []
    for i in range(8 if total > 0 else 0):           # 8 frames spread over the video decide the rotation
        cap.set(cv2.CAP_PROP_POS_FRAMES, total * (2 * i + 1) // 16)
        ok, frame = cap.read()
        if ok:
            samples.append(frame)
    cap.release()
    angle = upright_angle(engine, samples)

    cap = open_video(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    stem = safe_stem(path)
    index, saved, last = -1, 0, float("-inf")
    skipped = Counter()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        index += 1
        t = index / fps
        if t - last < interval:
            continue
        frame = rotate(frame, angle)
        status, _, reason = judge(engine, frame)
        if status != "ok":
            skipped[reason] += 1
            continue
        save(out / f"{stem}_{round(t * 1000):07d}.jpg", frame)
        saved, last = saved + 1, t
    cap.release()
    if index < 0:
        print(f"  {path.name}: không đọc được video. {IPHONE_HINT}")
        return
    turned = f", đã xoay {angle}°" if angle else ""
    print(f"  {path.name}: video {(index + 1) / fps:.0f} giây{turned} → lưu {saved} ảnh" + skipped_text(skipped))


def read_image(path):
    data = np.fromfile(str(path), np.uint8)          # cv2.imread fails on non-ASCII paths on Windows
    return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None


def from_photos(engine, paths, out):
    saved, skipped = 0, Counter()
    for path in paths:
        img = read_image(path)
        if img is None:
            skipped["Không đọc được file"] += 1
            continue
        img = rotate(img, upright_angle(engine, [img]))
        status, _, reason = judge(engine, img)
        if status != "ok":
            skipped[reason] += 1
            continue
        save(out / f"{safe_stem(path)}.jpg", img)
        saved += 1
    print(f"  {len(paths)} ảnh chụp → lưu {saved} ảnh" + skipped_text(skipped))


def from_folder(engine, root, session, interval):
    root = Path(root)
    if not root.is_dir():
        raise SystemExit(f"Chưa có thư mục {root}. Xếp file theo dạng {root}/<người>/<điều kiện>/...")
    layout = f"cần dạng <người>/<điều kiện>/file, điều kiện là {', '.join(CONDITIONS)}"
    for person in sorted(root.iterdir()):
        if person.name.lower() in IGNORED:
            continue
        if not person.is_dir():
            print(f"Bỏ qua {person.name}: {layout}")
            continue
        if not NAME.fullmatch(person.name):
            print(f"Bỏ qua {person.name}: tên người chỉ gồm chữ thường không dấu, số, _ hoặc -")
            continue
        for folder in sorted(person.iterdir()):
            if folder.name.lower() in IGNORED:
                continue
            if not folder.is_dir() or folder.name not in CONDITIONS:
                print(f"Bỏ qua {person.name}/{folder.name}: {layout}")
                continue
            print(f"{person.name}/{folder.name}:")
            out = TEAM_DIR / person.name / f"s{session}" / folder.name
            out.mkdir(parents=True, exist_ok=True)
            photos = []
            for f in sorted(folder.iterdir()):
                ext = f.suffix.lower()
                if not f.is_file() or f.name.lower() in IGNORED:
                    continue
                if ext in VIDEO_EXT:
                    from_video(engine, f, out, interval)
                elif ext in IMAGE_EXT:
                    photos.append(f)
                else:
                    print(f"  {f.name}: không phải video/ảnh" + (f". {IPHONE_HINT}" if ext in (".heic", ".heif") else ""))
            if photos:
                from_photos(engine, photos, out)


def from_webcam(engine, out, camera, seconds, interval):
    cam = cv2.VideoCapture(camera, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cam.isOpened():
        raise SystemExit(f"Không mở được camera {camera} (ứng dụng khác đang dùng? thử --camera 1)")

    print("Bắt đầu sau 3 giây. Quay đầu nhẹ trái, phải, ngẩng, cúi trong lúc quay.")
    start = time.monotonic() + 3
    saved, last_save, last_reason = 0, 0.0, ""
    while True:
        ok, frame = cam.read()
        if not ok:
            raise SystemExit("Mất tín hiệu camera")
        now = time.monotonic()
        view = frame.copy()
        status, face, reason = judge(engine, frame)
        color = GREEN if status == "ok" else RED
        if reason and reason != last_reason and face is not None:
            print(" ", reason)
        last_reason = reason or ""
        if status == "ok" and now >= start and now - last_save >= interval:
            save(out / f"{int(time.time() * 1000)}.jpg", frame)
            saved, last_save = saved + 1, now
        if face is not None:
            x, y, w, h = face.box.astype(int)
            cv2.rectangle(view, (x, y), (x + w, y + h), color, 2)
        label = (f"start in {start - now:.0f}s" if now < start
                 else f"saved {saved} | {max(0, start + seconds - now):.0f}s left")
        cv2.putText(view, label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(view, status, (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.imshow("YoloHome - collect faces (q: stop)", view)
        if (cv2.waitKey(1) & 0xFF) == ord("q") or now >= start + seconds:
            break
    cam.release()
    cv2.destroyAllWindows()
    print(f"Đã lưu {saved} ảnh lần này")


def print_summary(session):
    people = sorted(p.parent.name for p in TEAM_DIR.glob(f"*/s{session}") if p.is_dir())
    if not people:
        return
    print(f"\nSố ảnh buổi {session} (tính cả video, ảnh chụp và webcam) trong {TEAM_DIR}:")
    print(f"{'':12s}" + "".join(f"{c:>14s}" for c in CONDITIONS))
    low = no_glasses = False
    for person in people:
        cells = ""
        for c in CONDITIONS:
            n = len(list((TEAM_DIR / person / f"s{session}" / c).glob("*.jpg")))
            if c == "mask_glasses" and n == 0:              # only people who wear glasses record it
                no_glasses, cells = True, cells + f"{'-':>13s} "
            else:
                low |= n < MIN_IMAGES
                cells += f"{n:>13d}{'*' if n < MIN_IMAGES else ' '}"
        print(f"{person:12s}{cells}")
    if low:
        print(f"* dưới {MIN_IMAGES} ảnh: gửi thêm video/ảnh rồi chạy lại, hoặc quay thêm bằng webcam.")
    if no_glasses:
        print("- không có kính: bỏ qua kiểu mask_glasses, không sao.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--import", dest="folder", nargs="?", const=str(RAW_DIR),
                   help="xử lý mọi video/ảnh trong thư mục <người>/<điều kiện>/ (mặc định data/raw)")
    p.add_argument("--person", help="webcam: tên không dấu, ví dụ: an, binh_nguyen")
    p.add_argument("--condition", choices=CONDITIONS, help="webcam: điều kiện đang quay")
    p.add_argument("--session", type=int, choices=(1, 2), default=1,
                   help="1 = dữ liệu train (mặc định); 2 chỉ dùng khi muốn chạy evaluate.py")
    p.add_argument("--seconds", type=float, default=30, help="webcam: thời gian quay")
    p.add_argument("--interval", type=float, default=0.3, help="giây giữa hai ảnh lấy từ video/webcam")
    p.add_argument("--camera", type=int, default=0, help="webcam: số thứ tự camera")
    a = p.parse_args()
    if not a.folder:
        if not (a.person and a.condition):
            p.error("dùng --import, hoặc --person và --condition để quay bằng webcam")
        if not NAME.fullmatch(a.person):
            p.error("--person chỉ gồm chữ thường không dấu, số, _ hoặc -")

    engine = face_engine.FaceEngine()
    if a.folder:
        from_folder(engine, a.folder, a.session, a.interval)
    else:
        out = TEAM_DIR / a.person / f"s{a.session}" / a.condition
        out.mkdir(parents=True, exist_ok=True)
        from_webcam(engine, out, a.camera, a.seconds, a.interval)
    print_summary(a.session)


if __name__ == "__main__":
    main()
