from datetime import datetime, time, timedelta
from types import SimpleNamespace

from adafruit_mqtt import build_command, mqtt_client
from database import SessionLocal
from models import Device, SensorHistory
from scheduler import due_at, run_due


def device(client, kind):
    return next(d for d in client.get("/api/devices/").json() if d["type"] == kind)


def control(client, kind, **body):
    return client.post(f"/api/devices/{device(client, kind)['id']}/control", json=body)


def activity(client):
    return client.get("/api/activity/").json()


def test_auto_sends_auto_and_does_not_fake_the_mode(client, board):
    with mqtt_client._lock:
        mqtt_client._state["mode"] = "MANUAL_LOCKDOWN until 10:00"
    assert control(client, "fan", action="auto").json()["value"] == "AUTO"
    assert board[-1][1].startswith("AUTO:")
    assert device(client, "fan")["mode"].startswith("MANUAL")


def test_fan_state_changes_only_when_board_reports(client, board):
    r = control(client, "fan", action="set_speed", speed=60).json()
    assert r["mqtt_sent"] and device(client, "fan")["speed"] == 0
    mqtt_client.sync_fan_state_to_db(60)
    assert device(client, "fan")["speed"] == 60


def test_ack_updates_row_written_before_publish(client, monkeypatch):
    # Worst case of the race: the ACK is processed during publish().
    monkeypatch.setattr(mqtt_client, "connected", True)

    def publish(topic, payload, qos=0):
        cid = payload.split(":")[1]
        mqtt_client._handle_ack(f"fan:{cid}:0:40:U:SAFE")
        return SimpleNamespace(rc=0)

    monkeypatch.setattr(mqtt_client.client, "publish", publish)
    control(client, "fan", action="set_speed", speed=40)
    rows = activity(client)
    assert len(rows) == 1 and rows[0]["status"] == "REJECTED" and rows[0]["reason"] == "SAFE"


def test_offline_command_is_reported_as_not_sent(client, monkeypatch):
    monkeypatch.setattr(mqtt_client, "connected", False)
    assert control(client, "fan", action="off").json()["success"] is False
    assert activity(client)[0]["status"] == "OFFLINE"


def test_timeout_does_not_overwrite_ack(client, board):
    cid = control(client, "fan", action="off").json()["cmd_id"]
    mqtt_client._handle_ack(f"fan:{cid}:1:0:U")
    mqtt_client._emit("timeout", cid)
    assert activity(client)[0]["status"] == "OK"


def test_board_events_drive_alert_level(client):
    assert device(client, "led")["alert_level"] is None
    mqtt_client._handle_event("HOT:33.5")
    assert device(client, "led")["alert_level"] == "HOT"
    mqtt_client._handle_event("SAFETY:46.0")
    assert device(client, "led")["alert_level"] == "SAFETY"
    mqtt_client._handle_event("SAFETY_CLEAR:42.0")
    mqtt_client._handle_event("HOT_CLEAR:32.0")
    assert device(client, "led")["alert_level"] is None
    assert activity(client)[0]["device"] == "board"


def test_sensor_pair_is_merged_and_current_has_both(client):
    mqtt_client.save_sensor_data("temperature", "28.5")
    mqtt_client.save_sensor_data("humidity", "50")
    db = SessionLocal()
    assert db.query(SensorHistory).count() == 1
    db.close()
    now = client.get("/api/sensors/current").json()
    assert now["temperature"] == 28.5 and now["humidity"] == 50 and now["timestamp"].endswith("Z")


def test_current_handles_old_split_rows(client):
    db = SessionLocal()
    db.add_all([SensorHistory(temperature=30, recorded_at=datetime(2026, 1, 1, 0, 0, 0)),
                SensorHistory(humidity=60, recorded_at=datetime(2026, 1, 1, 0, 0, 1))])
    db.commit()
    db.close()
    now = client.get("/api/sensors/current").json()
    assert now["temperature"] == 30 and now["humidity"] == 60


def add_schedule(client, **kw):
    body = {"device_id": device(client, "fan")["id"], "action": "set_speed", "speed": 55,
            "scheduled_time": "07:30", "repeat_mode": "daily", **kw}
    return client.post("/api/schedules/", json=body)


def test_schedule_validation(client):
    assert add_schedule(client, speed=None).status_code == 400
    assert add_schedule(client, action="alert").status_code == 400
    assert add_schedule(client, repeat_mode="monthly").status_code == 400
    assert add_schedule(client).status_code == 200


def test_schedule_fires_once_as_schedule_with_hold(client, board):
    add_schedule(client)
    at = datetime(2030, 11, 6, 7, 30, 20)
    assert run_due(at - timedelta(minutes=1)) == 0
    assert run_due(at) == 1
    assert run_due(at + timedelta(seconds=15)) == 0     # second tick, same minute
    assert len(board) == 1
    value, _, actor, hold = board[0][1].split(":")
    assert (value, actor, hold) == ("55", "S", "30")
    assert run_due(at + timedelta(days=1)) == 1         # daily: again tomorrow


def test_once_deactivates_and_missed_run_is_skipped(client, board):
    add_schedule(client, repeat_mode="once")
    assert run_due(datetime(2030, 11, 6, 9, 0)) == 0    # long after 07:30
    assert run_due(datetime(2030, 11, 7, 7, 30)) == 1
    assert run_due(datetime(2030, 11, 8, 7, 30)) == 0
    assert client.get("/api/schedules/").json()[0]["is_active"] is False


def test_due_at_weekly_uses_creation_weekday():
    s = SimpleNamespace(is_active=True, scheduled_time=time(7, 30), repeat_mode="weekly",
                        created_at=datetime(2026, 11, 2, 1, 0), last_run_at=None)  # Monday
    assert due_at(s, datetime(2026, 11, 9, 7, 30)) is not None
    assert due_at(s, datetime(2026, 11, 10, 7, 30)) is None


def test_auto_payload_contract():
    assert build_command("fan", "auto", "USER", cmd_id="abcd1234")[0] == "AUTO:abcd1234:U"


def test_devices_seeded_once(client):
    db = SessionLocal()
    assert db.query(Device).count() == 2
    db.close()


def test_schedule_during_lockdown_sends_auto_and_schedule(client, board):
    with mqtt_client._lock:
        mqtt_client._state["mode"] = "MANUAL_LOCKDOWN until 12:00"
    add_schedule(client, speed=60)
    at = datetime(2030, 11, 6, 7, 30, 20)
    assert run_due(at) == 1
    assert len(board) == 2
    assert board[0][1].startswith("AUTO:")
    assert board[1][1].startswith("60:")
    assert board[1][1].split(":")[2] == "S"


def test_fire_status_endpoint_and_tinyml_event(client):
    mqtt_client._handle_event("TINYML:ALERT:0.95")
    res = client.get("/api/sensors/fire-status").json()
    assert res["state"] == "ALERT"
    assert res["is_alarm"] is True
    assert res["score"] == 0.95


