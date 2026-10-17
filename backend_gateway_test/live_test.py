"""Live test: backend client <-> real Adafruit IO <-> Yolo Uno running the bare-board demo.

    pip install "paho-mqtt>=2.0,<3" python-dotenv
    python live_test.py            (adafruit_mqtt.py and .env in the same folder)

Sends an LED colour and a fan command, prints everything the board sends back, and logs
round-trip times to data/command_latency.csv. No database needed.
"""
import logging
import os
import sys
import time
import types

# Stand-ins for the app's database layer, so the client runs without PostgreSQL.
saved_rows = []


class FakeSession:
    def add(self, row): saved_rows.append(row)
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


class SensorHistory:
    def __init__(self, **kw): self.__dict__.update(kw)


sys.modules.setdefault("database", types.SimpleNamespace(SessionLocal=FakeSession))
sys.modules.setdefault("models", types.SimpleNamespace(SensorHistory=SensorHistory))

import adafruit_mqtt  # noqa: E402  (reads .env on import)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
LISTEN_S = int(os.getenv("LIVE_TEST_SECONDS", "70"))   # light arrives every 30 s
c = adafruit_mqtt.mqtt_client


def show_ack(a):
    print(f"  ACK    {a['device']} id={a['cmd_id']} ok={a['ok']} value={a['value']} "
          f"actor={a['actor']} reason={a['reason']} round-trip={a['rtt_ms']} ms")


c.on("ack", show_ack)
c.on("sensor", lambda s: print(f"  SENSOR {s['kind']} = {s.get('value')}"))
c.on("mode", lambda m: print(f"  MODE   {m}"))
c.on("event", lambda e: print(f"  EVENT  {e['type']}: {e['data']}"))

if not c.connect():
    sys.exit("Set ADAFRUIT_IO_USERNAME and ADAFRUIT_IO_KEY in .env")
for _ in range(100):
    if c.connected:
        break
    time.sleep(0.1)
else:
    sys.exit("Could not connect to Adafruit IO within 10 s: check the key and your network")
time.sleep(1)                                         # let the subscriptions settle

print("\n1) LED -> #FF0000 (the RGB LED should turn red)")
print(f"   sent, command id = {c.send_command('led', '#653700', actor='USER')}")
time.sleep(5)
print("\n2) fan -> 70 as a voice command (bare board has no fan: expect ok=False reason=NOHW)")
print(f"   sent, command id = {c.send_command('fan', 70, actor='VOICE')}")

print(f"\n3) listening {LISTEN_S} s for telemetry (Ctrl+C to stop early)")
try:
    time.sleep(LISTEN_S)
except KeyboardInterrupt:
    pass
print("\nstate:", c.get_state())
print("stats:", c.stats)
print("latency log:", c.latency_log.resolve())
c.disconnect()