"""
Adafruit IO MQTT connection manager for the backend.

Talks to the board through Adafruit IO. The message formats (section 1 below) must match
the firmware (adafruitio_task.h); both are tested against contract/cloud_vectors.txt.

What changed from the previous version, and why:
  * TLS on port 8883. Port 1883 sent the Adafruit key in plain text.
  * paho-mqtt 2.x callback API (VERSION1 is deprecated).
  * send_command(): validates the value, tags the command with an id and an actor
    (USER / VOICE / SCHEDULE), and refuses anything that could overflow the board's 45-byte
    buffer. Plain publish("yolohome-fan", "1") used to set the fan to 1 %, and a schedule
    looked like a user command, which started a 30-minute Manual Lockdown.
  * ACKs from the board are matched to commands: the round-trip time is logged to
    data/command_latency.csv (evidence for NFR-01), and handlers receive device/actor/result
    for the activity log (Module 4).
  * Offline backlog from the board is stored with its ORIGINAL timestamp.
  * Subscribes to exactly the feeds it needs, not "#" (which also echoed our own commands).
  * The DB session is always closed, also when saving fails.

Usage from routes:
    from adafruit_mqtt import mqtt_client
    cmd_id = mqtt_client.send_command("fan", 70, actor="VOICE")   # None if offline
    mqtt_client.on("ack", lambda ack: ...)                        # write the activity log
    mqtt_client.get_state()   # {'fan_state': 70, 'mode': 'AUTO_AI', ...}
"""
import csv
import logging
import math
import os
import re
import secrets
import threading
import time
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from paho.mqtt.enums import CallbackAPIVersion

from database import SessionLocal
from models import SensorHistory

load_dotenv()
log = logging.getLogger("adafruit_mqtt")

# =====================================================================================
# 1. Message formats (mirror of the firmware, firmware/include/adafruitio_task.h)
#
# Why not JSON: the board uses the Adafruit IO Arduino library, which copies every feed value
# into a 45-byte buffer with strcpy() (no bounds check) and parses values as CSV. A value of
# 45+ characters corrupts memory on the board; a comma splits it. So every value on a feed the
# board subscribes to must be <= 44 characters with no ',' or '"'. build_command() enforces it.
#
#     command  backend -> board   "<value>:<id>:<actor>[:<hold_min>]"      "70:a1b2c3d4:S"
#     ack      board -> backend   "<dev>:<id|->:<1|0>:<value>:<actor>[:<reason>]"
#     event    board -> backend   "<TYPE>:<data>"                          "SAFETY:46.2"
#     backlog  board -> backend   "B:<epoch|0>:<temp>:<humi>:<light>:<presence>"
# =====================================================================================
MAX_VALUE = 44
ACTOR_CODES = {"USER": "U", "VOICE": "V", "SCHEDULE": "S", "SYNC": "Y", "AI": "A", "SYSTEM": "X"}
CODE_ACTORS = {v: k for k, v in ACTOR_CODES.items()}
SENDABLE_ACTORS = ("USER", "VOICE", "SCHEDULE")   # AI/SYSTEM/SYNC originate on the board only
DEVICES = ("fan", "led", "relay")
_ID = re.compile(r"[0-9A-Za-z]{1,8}")
_HEX6 = re.compile(r"#?[0-9A-Fa-f]{6}")


class CommandError(ValueError):
    """The command can't be sent as given (bad device, value, actor or length)."""


def feed_safe(text: str) -> bool:
    """True if `text` can go on a feed the board subscribes to without harming it."""
    return (0 < len(text) <= MAX_VALUE and "," not in text and '"' not in text
            and all(ord(c) >= 0x20 for c in text))


def normalize_value(device: str, value) -> str:
    if device not in DEVICES:
        raise CommandError(f"unknown device {device!r}")
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    s = str(value).strip()
    u = s.upper()
    if u in ("ON", "TRUE"):
        return "ON"
    if u in ("OFF", "FALSE"):
        return "OFF"
    if device == "fan":
        try:
            f = float(s)
        except ValueError:
            raise CommandError(f"fan value must be 0-100, ON or OFF, not {value!r}") from None
        if math.isnan(f) or not 0 <= f <= 100:
            raise CommandError(f"fan value must be 0-100, not {value!r}")
        return str(int(round(f)))       # round-half-even, same as the board
    if device == "led":
        if u in ("1", "0"):
            return "ON" if u == "1" else "OFF"
        if _HEX6.fullmatch(s):
            return "#" + s.lstrip("#").upper()
        raise CommandError(f"led value must be #RRGGBB, ON or OFF, not {value!r}")
    if u in ("1", "0"):                 # relay
        return "ON" if u == "1" else "OFF"
    raise CommandError(f"relay value must be ON or OFF, not {value!r}")


def build_command(device: str, value, actor: str = "USER", cmd_id: Optional[str] = None,
                  hold_min: Optional[float] = None) -> tuple:
    """Returns (payload, cmd_id). Raises CommandError if the command can't be sent safely."""
    actor = str(actor).upper()
    if actor not in SENDABLE_ACTORS:
        raise CommandError(f"actor {actor!r} cannot be sent from the backend "
                           f"(allowed: {', '.join(SENDABLE_ACTORS)})")
    cmd_id = cmd_id or secrets.token_hex(4)
    if not _ID.fullmatch(cmd_id):
        raise CommandError(f"command id must be 1-8 letters/digits, not {cmd_id!r}")
    payload = f"{normalize_value(device, value)}:{cmd_id}:{ACTOR_CODES[actor]}"
    if hold_min is not None:
        if not 0 <= float(hold_min) <= 1440:
            raise CommandError("hold_min must be between 0 and 1440")
        payload += f":{int(round(float(hold_min)))}"
    if not feed_safe(payload):
        raise CommandError(f"payload {payload!r} is not safe for the board")
    return payload, cmd_id


@dataclass(frozen=True)
class Ack:
    device: str
    cmd_id: Optional[str]          # None for commands typed on the Adafruit dashboard
    ok: bool
    value: str
    actor: str                     # USER / VOICE / SCHEDULE / SYNC / AI / SYSTEM
    reason: Optional[str]          # LOCK, SAFE, BAD, BUSY, ... on rejection


def parse_ack(text: str) -> Ack:
    parts = text.strip().split(":")
    if len(parts) not in (5, 6):
        raise ValueError(f"not an ACK: {text!r}")
    dev, cid, ok, value, actor = parts[:5]
    if dev not in DEVICES or ok not in ("0", "1") or actor not in CODE_ACTORS:
        raise ValueError(f"not an ACK: {text!r}")
    reason = parts[5] if len(parts) == 6 and parts[5] else None
    return Ack(dev, None if cid == "-" else cid, ok == "1", value, CODE_ACTORS[actor], reason)


@dataclass(frozen=True)
class Backlog:
    recorded_at: Optional[datetime]  # UTC; None if the board's clock was never synced
    temperature: float
    humidity: float
    light: int
    presence: bool


def parse_event(text: str) -> tuple:
    """'SAFETY:46.2' -> ('SAFETY', '46.2');  'B:...' -> ('B', Backlog(...))."""
    kind, _, data = text.strip().partition(":")
    if not kind:
        raise ValueError(f"empty event: {text!r}")
    if kind != "B":
        return kind, data
    p = data.split(":")
    if len(p) != 5:
        raise ValueError(f"bad backlog entry: {text!r}")
    epoch = int(p[0])
    when = datetime.fromtimestamp(epoch, timezone.utc) if epoch else None
    return "B", Backlog(when, float(p[1]), float(p[2]), int(p[3]), p[4] == "1")


# =====================================================================================
# 2. The client
# =====================================================================================

AIO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME", "")
AIO_KEY = os.getenv("ADAFRUIT_IO_KEY", "")
AIO_HOST = os.getenv("ADAFRUIT_IO_HOST", "io.adafruit.com")
AIO_PORT = int(os.getenv("ADAFRUIT_IO_PORT", "8883"))
AIO_TLS = os.getenv("ADAFRUIT_IO_TLS", "1") != "0"

# Must match firmware/include/cloud_config.h. Exactly 10 feeds: the free-tier maximum.
_DEFAULT_FEEDS = {
    "temperature": "yolohome-temperature",
    "humidity": "yolohome-humidity",
    "light": "yolohome-light",
    "presence": "yolohome-presence",
    "fan": "yolohome-fan",               # command
    "led": "yolohome-led",               # command
    "ack": "yolohome-ack",
    "event": "yolohome-event",
    "mode": "yolohome-mode",
    "fan_state": "yolohome-fan-state",
}
FEEDS = {name: os.getenv(f"AIO_FEED_{name.upper()}", key) for name, key in _DEFAULT_FEEDS.items()}
COMMAND_DEVICES = ("fan", "led")
ACK_TIMEOUT_S = 30.0
LATENCY_LOG = Path(os.getenv("AIO_LATENCY_LOG", "data/command_latency.csv"))
_LATENCY_HEADER = ["sent_at_utc", "cmd_id", "device", "value", "actor", "ok", "reason", "rtt_ms"]


def _utcnow_naive():
    """Naive UTC, same convention the previous code stored (datetime.utcnow())."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AdafruitMQTTClient:
    def __init__(self, username=AIO_USERNAME, key=AIO_KEY, host=AIO_HOST, port=AIO_PORT,
                 tls=AIO_TLS, feeds=None, latency_log=LATENCY_LOG):
        self.username, self.key, self.host, self.port = username, key, host, port
        self.feeds = dict(feeds or FEEDS)
        self.latency_log = Path(latency_log)
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2,
                                  client_id=f"yolohome-backend-{secrets.token_hex(3)}")
        if username:
            self.client.username_pw_set(username, key)
        if tls:
            self.client.tls_set()
        self.client.reconnect_delay_set(1, 30)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        self.tls = tls
        self.connected = False
        self._lock = threading.Lock()          # pending commands and state
        self._file_lock = threading.Lock()     # latency CSV (always taken after _lock)
        self._pending = {}             # cmd_id -> (monotonic sent, sent_at, device, value, actor)
        self._handlers = {k: [] for k in ("ack", "event", "mode", "fan_state", "sensor")}
        self._state = {"fan_state": None, "mode": None, "last_event": None, "updated_at": None}
        self.stats = {"commands": 0, "acks": 0, "ack_timeouts": 0, "throttled": 0,
                      "bad_messages": 0, "backlog_rows": 0}
        self._topics = {f"{username}/feeds/{key}": name for name, key in self.feeds.items() if key}

    # ---- public API -------------------------------------------------------------------
    def on(self, kind, handler):
        """Register handler(payload) for 'ack', 'event', 'mode', 'fan_state' or 'sensor'."""
        self._handlers[kind].append(handler)

    def get_state(self):
        with self._lock:
            return dict(self._state)

    def send_command(self, device, value, actor="USER", hold_min=None):
        """Send a fan/LED command. Returns the command id, or None if not connected.
        Raises CommandError (a ValueError) for an invalid device, value or actor."""
        if device not in COMMAND_DEVICES or not self.feeds.get(device):
            raise CommandError(f"no command feed for {device!r} (free tier: 10 feeds)")
        payload, cmd_id = build_command(device, value, actor, hold_min=hold_min)
        if not self.connected:
            log.warning("not connected to Adafruit IO; %s command dropped", device)
            return None
        sent = (time.monotonic(), _utcnow_naive(), device, payload.split(":")[0], actor.upper())
        with self._lock:
            self._expire_pending_locked()
            self._pending[cmd_id] = sent
        info = self.client.publish(self._topic(device), payload, qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            with self._lock:
                self._pending.pop(cmd_id, None)
            log.error("publish failed (rc=%s)", info.rc)
            return None
        self.stats["commands"] += 1
        log.info("📤 %s = %s", device, payload)
        return cmd_id

    def publish(self, feed, value):
        """Deprecated: use send_command(). Kept so existing routes keep working.
        For the fan, the old convention "1"/"0" = on/off is honoured here (send_command
        treats 1 as 1 %)."""
        warnings.warn("publish() is deprecated; use send_command()", DeprecationWarning,
                      stacklevel=2)
        device = next((d for d in COMMAND_DEVICES if self.feeds.get(d) == feed), None)
        if device:
            if device == "fan" and str(value).strip() in ("1", "0"):
                value = "ON" if str(value).strip() == "1" else "OFF"
            return self.send_command(device, value) is not None
        text = str(value)
        if not feed_safe(text):        # the board subscribes to all its feeds
            log.error("refusing to publish %r to %s: not safe for the board", text, feed)
            return False
        if not self.connected:
            return False
        return self.client.publish(f"{self.username}/feeds/{feed}", text, qos=1).rc == \
            mqtt.MQTT_ERR_SUCCESS

    def connect(self):
        if not self.username or not self.key:
            log.error("ADAFRUIT_IO_USERNAME / ADAFRUIT_IO_KEY not set")
            return False
        log.info("🔌 Connecting to %s:%s (TLS=%s)", self.host, self.port, self.tls)
        self.client.connect_async(self.host, self.port, keepalive=60)   # retries on its own
        self.client.loop_start()
        return True

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        log.info("👋 Disconnected from Adafruit IO")

    # ---- paho callbacks (network thread) ------------------------------------------------
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("❌ Adafruit IO refused the connection: %s", reason_code)
            return
        self.connected = True
        subs = [t for t, name in self._topics.items() if name not in COMMAND_DEVICES]
        subs += [f"{self.username}/throttle", f"{self.username}/errors"]
        client.subscribe([(t, 1) for t in subs])
        log.info("✅ Connected to Adafruit IO, subscribed to %d topics", len(subs))

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        if reason_code.is_failure:
            log.warning("⚠️ Lost Adafruit IO (%s); paho will reconnect", reason_code)
        else:
            log.info("Disconnected from Adafruit IO")

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", "replace").strip()
        if msg.topic.endswith("/throttle"):
            self.stats["throttled"] += 1
            log.warning("Adafruit IO throttle: %s", payload)
            return
        if msg.topic.endswith("/errors"):
            log.error("Adafruit IO error: %s", payload)
            return
        name = self._topics.get(msg.topic)
        try:
            if name in ("temperature", "humidity"):
                self.save_sensor_data(name, payload)
            elif name in ("light", "presence"):
                self._emit("sensor", {"kind": name, "value": payload, "replayed": False})
            elif name == "ack":
                self._handle_ack(payload)
            elif name == "event":
                self._handle_event(payload)
            elif name in ("mode", "fan_state"):
                value = int(payload) if name == "fan_state" else payload
                with self._lock:
                    self._state[name] = value
                    self._state["updated_at"] = _utcnow_naive()
                self._emit(name, value)
        except ValueError as e:
            self.stats["bad_messages"] += 1
            log.warning("ignored malformed %s message %r: %s", name, payload, e)

    # ---- internals ----------------------------------------------------------------------
    def _topic(self, name):
        return f"{self.username}/feeds/{self.feeds[name]}"

    def _emit(self, kind, payload):
        for h in self._handlers[kind]:
            try:
                h(payload)
            except Exception:          # a broken handler must not kill the network thread
                log.exception("%s handler failed", kind)

    def _handle_ack(self, payload):
        ack = parse_ack(payload)
        with self._lock:
            self._expire_pending_locked()
            sent = self._pending.pop(ack.cmd_id, None) if ack.cmd_id else None
        rtt_ms = round((time.monotonic() - sent[0]) * 1000, 1) if sent else None
        sent_at = sent[1] if sent else None
        self.stats["acks"] += 1
        self._log_latency([sent_at.isoformat() if sent_at else "", ack.cmd_id or "", ack.device,
                           ack.value, ack.actor, int(ack.ok), ack.reason or "",
                           rtt_ms if rtt_ms is not None else ""])
        self._emit("ack", {"cmd_id": ack.cmd_id, "device": ack.device, "ok": ack.ok,
                           "value": ack.value, "actor": ack.actor, "reason": ack.reason,
                           "rtt_ms": rtt_ms, "sent_at": sent_at})

    def _expire_pending_locked(self):
        now = time.monotonic()
        for cid, (t, sent_at, device, value, actor) in list(self._pending.items()):
            if now - t > ACK_TIMEOUT_S:
                del self._pending[cid]
                self.stats["ack_timeouts"] += 1
                self._log_latency([sent_at.isoformat(), cid, device, value, actor, "",
                                   "NO_ACK", ""])
                log.warning("no ACK for %s command %s after %.0f s", device, cid, ACK_TIMEOUT_S)

    def _handle_event(self, payload):
        kind, data = parse_event(payload)
        if kind == "B":                # a minute buffered by the board while it was offline
            when = data.recorded_at.replace(tzinfo=None) if data.recorded_at else None
            self.save_sensor_row(data.temperature, data.humidity, when)
            self.stats["backlog_rows"] += 1
            self._emit("sensor", {"kind": "backlog", "light": data.light,
                                  "presence": data.presence, "recorded_at": when,
                                  "replayed": True})
            return
        with self._lock:
            self._state["last_event"] = (kind, data)
        log.warning("⚠️ board event %s: %s", kind, data)
        self._emit("event", {"type": kind, "data": data})

    def _log_latency(self, row):
        try:
            with self._file_lock:
                new = not self.latency_log.exists()
                self.latency_log.parent.mkdir(parents=True, exist_ok=True)
                with self.latency_log.open("a", newline="") as f:
                    w = csv.writer(f)
                    if new:
                        w.writerow(_LATENCY_HEADER)
                    w.writerow(row)
        except OSError:
            log.exception("cannot write %s", self.latency_log)

    # ---- database (same table and conventions as before) ---------------------------------
    def save_sensor_data(self, kind, value):
        """One live reading per row, as the previous version did."""
        v = float(value)               # ValueError -> on_message logs and ignores it
        self._save(SensorHistory(temperature=v if kind == "temperature" else None,
                                 humidity=v if kind == "humidity" else None,
                                 recorded_at=_utcnow_naive()))

    def save_sensor_row(self, temperature, humidity, recorded_at=None):
        """Both values in one row (backlog entries are already aligned)."""
        self._save(SensorHistory(temperature=temperature, humidity=humidity,
                                 recorded_at=recorded_at or _utcnow_naive()))

    def _save(self, row):
        db = SessionLocal()
        try:
            db.add(row)
            db.commit()
        except Exception:
            db.rollback()
            log.exception("❌ could not save sensor data")
        finally:
            db.close()


# Global instance (imported by main.py and the routes)
mqtt_client = AdafruitMQTTClient()