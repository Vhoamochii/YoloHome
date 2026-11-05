import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from protocol import parse_frame, event_value, validate_feed_value


def frame(**updates):
    f = dict(type="tinyml_fire", v=1, seq=1, uptime_ms=2000, temperature=28.0, humidity=65.0,
             score=.001, valid=True, ml_alarm=False, heat_alarm=False, alarm=False,
             state="OK", model="18a0faee2146", inference_us=10, simulated=False)
    f.update(updates)
    return f


class ProtocolTests(unittest.TestCase):
    def test_normal(self):
        f = parse_frame(json.dumps(frame()))
        self.assertEqual(event_value(f), "TINYML:OK:0.001")

    def test_error_retains_alarm(self):
        f = frame(valid=False, state="SENSOR_ERROR", temperature=None, humidity=None, score=None,
                  alarm=True, heat_alarm=True)
        self.assertTrue(parse_frame(json.dumps(f))["alarm"])
        self.assertTrue(validate_feed_value(event_value(f)))

    def test_reject_bad_data(self):
        for changes in [dict(temperature=float("nan")), dict(humidity=101), dict(score=2),
                        dict(valid="true"), dict(seq=True), dict(state="ALERT"), dict(alarm=True),
                        dict(model="unknown"), dict(type="other")]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_frame(json.dumps(frame(**changes)))

    def test_mqtt_value_limits(self):
        for state in ("OK", "ALERT", "SENSOR_ERROR"):
            self.assertTrue(validate_feed_value(event_value(frame(state=state))))
        for value in ["x" * 45, "a,b", 'a"b', "a\nb", ""]:
            self.assertFalse(validate_feed_value(value))

    def test_cloud_refuses_simulation(self):
        from serial_gateway import Cloud
        cloud = object.__new__(Cloud)
        cloud.up = True
        cloud.publish = lambda *a: self.fail("simulated data was published")
        cloud.handle(frame(simulated=True))

    def test_install_refuses_existing_directory(self):
        import tempfile
        from install_addon import install
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "backend").mkdir()
            (root / "backend/adafruit_mqtt.py").touch()
            (root / "firmware/src").mkdir(parents=True)
            (root / "firmware/src/main.cpp").touch()
            (root / "tinyml-fire").mkdir()
            with self.assertRaises(FileExistsError):
                install(root / "source", root)


if __name__ == "__main__":
    unittest.main()
