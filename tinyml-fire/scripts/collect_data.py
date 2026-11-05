"""Collect labeled REAL sensor readings. Label is supplied by the experimenter."""
import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from protocol import parse_frame


def main():
    import serial
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", required=True)
    p.add_argument("--label", required=True, type=int, choices=(0, 1))
    p.add_argument("--session", required=True, help="Independent experiment id; do not reuse across experiments")
    p.add_argument("--seconds", type=int, default=120)
    p.add_argument("--out", type=Path, default=Path("data/labeled/readings.csv"))
    a = p.parse_args()
    if a.seconds <= 0 or not a.session.strip():
        p.error("positive --seconds and a non-empty --session are required")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    new = not a.out.exists() or a.out.stat().st_size == 0
    fields = ["temperature", "humidity", "label", "session_id", "recorded_at_utc"]
    n = 0
    with a.out.open("a", newline="", encoding="utf-8") as f, serial.Serial(a.port, 115200, timeout=1) as ser:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        stop = time.monotonic() + a.seconds
        while time.monotonic() < stop:
            try:
                frame = parse_frame(ser.read_until(b"\n", size=2049).decode().strip())
            except (ValueError, UnicodeError, TypeError):
                continue
            if not frame["valid"] or frame["simulated"]:
                continue
            w.writerow(dict(temperature=frame["temperature"], humidity=frame["humidity"],
                            label=a.label, session_id=a.session,
                            recorded_at_utc=datetime.now(timezone.utc).isoformat()))
            f.flush()
            n += 1
    print(f"Saved {n} real readings to {a.out}")
    if not n:
        raise SystemExit("No valid real readings. Check firmware/port/sensor.")


if __name__ == "__main__":
    main()
