"""Read board inference via USB. Optional TLS publisher for standalone firmware only."""
import argparse
import csv
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from protocol import parse_frame, event_value, validate_feed_value

LOG = logging.getLogger("tinyml_gateway")
FIELDS = ["received_at_utc", "seq", "uptime_ms", "temperature", "humidity", "score",
          "valid", "ml_alarm", "heat_alarm", "alarm", "state", "model", "inference_us", "simulated"]


class Cloud:
    def __init__(self):
        import paho.mqtt.client as mqtt
        self.user = os.getenv("ADAFRUIT_IO_USERNAME", "")
        key = os.getenv("ADAFRUIT_IO_KEY", "")
        if not self.user or not key:
            raise ValueError("Set ADAFRUIT_IO_USERNAME and ADAFRUIT_IO_KEY in .env")
        self.feeds = {k: os.getenv("AIO_FEED_" + k.upper(), "yolohome-" + k)
                      for k in ("temperature", "humidity", "event")}
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.username_pw_set(self.user, key)
        self.client.tls_set()  # certificate verification stays enabled
        self.client.reconnect_delay_set(1, 30)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.up = False
        self.paused_until = 0
        self.client.connect_async("io.adafruit.com", 8883, keepalive=60)
        self.client.loop_start()
        self.last_telemetry = self.last_event = float("-inf")
        self.reported = None

    def on_connect(self, client, userdata, flags, reason, properties):
        self.up = not reason.is_failure
        if self.up:
            client.subscribe([(self.user + "/throttle", 0), (self.user + "/errors", 0)])
        LOG.info("Cloud connected=%s", self.up)

    def on_disconnect(self, client, userdata, flags, reason, properties):
        self.up = False
        LOG.warning("Cloud disconnected; edge inference continues")

    def on_message(self, client, userdata, msg):
        LOG.warning("Adafruit %s: %s", msg.topic.rsplit("/", 1)[-1], msg.payload.decode(errors="replace"))
        if msg.topic.endswith("/throttle"):
            self.paused_until = time.monotonic() + 60

    def publish(self, name, value):
        if not validate_feed_value(value):
            raise ValueError("Unsafe feed payload")
        # QoS 0: do not queue stale readings while disconnected.
        return self.client.publish(f"{self.user}/feeds/{self.feeds[name]}", value, qos=0).rc == 0

    def handle(self, frame):
        if frame["simulated"] or not self.up:
            return
        now = time.monotonic()
        if now < self.paused_until:
            return
        # <=12 telemetry + 2 events/minute; the account's other publishers share its quota.
        if frame["valid"] and now - self.last_telemetry >= 10:
            self.publish("temperature", f'{frame["temperature"]:.3f}')
            self.publish("humidity", f'{frame["humidity"]:.3f}')
            self.last_telemetry = now
        if now - self.last_event >= 30 and (frame["state"] != self.reported or now - self.last_event >= 60):
            if self.publish("event", event_value(frame)):
                self.reported = frame["state"]
                self.last_event = now

    def close(self):
        self.client.disconnect()
        self.client.loop_stop()


def run(args):
    import serial
    from serial.tools import list_ports
    if args.list_ports:
        for p in list_ports.comports():
            print(p.device, p.description)
        return
    if not args.port:
        raise ValueError("Choose --port COMx (use --list-ports first)")
    from dotenv import load_dotenv
    load_dotenv(args.env)
    cloud = Cloud() if args.cloud else None
    args.log.parent.mkdir(parents=True, exist_ok=True)
    new = not args.log.exists() or args.log.stat().st_size == 0
    try:
        with args.log.open("a", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=FIELDS, extrasaction="ignore")
            if new:
                writer.writeheader()
            while True:
                try:
                    with serial.Serial(args.port, 115200, timeout=1) as ser:
                        LOG.info("Listening on %s; Ctrl+C to exit", args.port)
                        last_rx = time.monotonic()
                        warned = False
                        while True:
                            raw = ser.read_until(b"\n", size=2049)
                            if not raw:
                                if time.monotonic() - last_rx > 8 and not warned:
                                    LOG.error("No frames for 8 s: USB/board may be disconnected")
                                    warned = True
                                continue
                            try:
                                frame = parse_frame(raw.decode("utf-8").strip())
                            except (ValueError, UnicodeError, TypeError):
                                LOG.debug("Ignored non-frame / malformed line")
                                continue
                            last_rx = time.monotonic()
                            warned = False
                            frame["received_at_utc"] = datetime.now(timezone.utc).isoformat()
                            writer.writerow(frame)
                            out.flush()
                            print(json.dumps(frame, ensure_ascii=False), flush=True)
                            if cloud:
                                cloud.handle(frame)
                except (serial.SerialException, OSError) as exc:
                    LOG.error("USB unavailable (%s); retry in 2 s", exc)
                    time.sleep(2)
    finally:
        if cloud:
            cloud.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list-ports", action="store_true")
    p.add_argument("--port")
    p.add_argument("--cloud", action="store_true", help="Standalone only; never with integration firmware")
    p.add_argument("--env", type=Path, default=Path(__file__).resolve().parents[1] / ".env")
    p.add_argument("--log", type=Path, default=Path("data/captures/telemetry.csv"))
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    try:
        run(args)
    except KeyboardInterrupt:
        print("Stopped")
    except ValueError as exc:
        p.error(str(exc))
