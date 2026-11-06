import os
import sys
import tempfile
import types
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["ADAFRUIT_IO_USERNAME"] = ""      # main.py must not reach the real broker
os.environ["ADAFRUIT_IO_KEY"] = ""
os.environ["AIO_LATENCY_LOG"] = os.path.join(tempfile.mkdtemp(), "latency.csv")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    import cv2  # noqa: F401
except ImportError:                          # only the face routes use it
    sys.modules["cv2"] = types.ModuleType("cv2")

import pytest
from fastapi.testclient import TestClient

import main
from adafruit_mqtt import mqtt_client
from database import Base, engine


class FakeInfo:
    rc = 0


@pytest.fixture()
def board(monkeypatch):
    """Connected client whose publishes are recorded instead of sent."""
    sent = []
    monkeypatch.setattr(mqtt_client, "connected", True)
    monkeypatch.setattr(mqtt_client.client, "publish",
                        lambda topic, payload, qos=0: sent.append((topic, payload)) or FakeInfo())
    return sent


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(main.app) as c:
        with mqtt_client._lock:
            mqtt_client._pending.clear()
            mqtt_client._state.update(fan_state=None, mode=None, hot=False, safety=False)
        yield c
