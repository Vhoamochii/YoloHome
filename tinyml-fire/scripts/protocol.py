"""Strict board frame parsing and the group's existing MQTT event contract."""
import json
import math

STATES = {"OK", "ALERT", "SENSOR_ERROR"}


def parse_frame(line):
    if len(line) > 2048:
        raise ValueError("Oversized frame")
    f = json.loads(line)
    if not isinstance(f, dict) or f.get("type") != "tinyml_fire" or f.get("v") != 1:
        raise ValueError("Not a tinyml_fire v1 frame")
    for key in ("valid", "alarm", "ml_alarm", "heat_alarm", "simulated"):
        if type(f.get(key)) is not bool:
            raise ValueError("Invalid flag " + key)
    for key in ("seq", "uptime_ms", "inference_us"):
        if type(f.get(key)) is not int or not 0 <= f[key] <= 0xFFFFFFFF:
            raise ValueError("Invalid counter " + key)
    if f.get("state") not in STATES:
        raise ValueError("Invalid state")
    model = f.get("model")
    if not isinstance(model, str) or len(model) != 12 or any(c not in "0123456789abcdef" for c in model):
        raise ValueError("Invalid model id")
    if f["alarm"] != (f["ml_alarm"] or f["heat_alarm"]):
        raise ValueError("Inconsistent alarm flags")
    if f["valid"]:
        for key, lo, hi in (("temperature", -40, 80), ("humidity", 0, 100), ("score", 0, 1)):
            val = f.get(key)
            if type(val) not in (int, float) or not math.isfinite(val) or not lo <= val <= hi:
                raise ValueError("Invalid " + key)
        if f["state"] != ("ALERT" if f["alarm"] else "OK"):
            raise ValueError("Inconsistent state")
    elif f["state"] != "SENSOR_ERROR" or any(f.get(k) is not None for k in ("temperature", "humidity", "score")):
        raise ValueError("Invalid error frame")
    return f


def event_value(frame):
    score = f'{frame["score"]:.3f}' if frame["valid"] else "-1.000"
    return f'TINYML:{frame["state"]}:{score}'


def validate_feed_value(value):
    return 0 < len(value) <= 44 and not any(c in value for c in ',"') and all(ord(c) >= 32 for c in value)
