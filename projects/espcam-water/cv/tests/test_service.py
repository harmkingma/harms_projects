import dataclasses
import datetime as dt
import json
import pathlib

import cv2
import pytest

from watermeter.service import Options, WaterMeterService

CFG = pathlib.Path(__file__).resolve().parents[1] / "meter.yaml"


class FakeCamera:
    def __init__(self, jpeg: bytes):
        self.jpeg, self.fail, self.frame_ts = jpeg, False, None

    def capture(self) -> bytes:
        if self.fail:
            raise OSError("timed out")
        return self.jpeg


class FakeMqtt:
    def __init__(self):
        self.messages: dict[str, object] = {}
        self.log: list[tuple[str, object]] = []

    def publish(self, topic, payload, retain=False):
        self.messages[topic] = payload
        self.log.append((topic, payload))


@pytest.fixture
def svc(tmp_path):
    ref = cv2.imread(str(CFG.parent / "reference" / "ref_mounted.jpg"))
    cam = FakeCamera(cv2.imencode(".jpg", ref)[1].tobytes())
    return WaterMeterService(Options(start_value=705.33, keep_rejected=2), CFG, tmp_path / "data",
                             tmp_path / "share", cam, FakeMqtt())


def test_discovery_entities(svc):
    svc.discovery()
    total = json.loads(svc.mqtt.messages["homeassistant/sensor/water_meter/total/config"])
    assert total["state_class"] == "total_increasing" and total["device_class"] == "water"
    assert total["default_entity_id"] == "sensor.water_meter_total"
    number = json.loads(svc.mqtt.messages["homeassistant/number/water_meter/set_value/config"])
    assert number["default_entity_id"] == "number.water_meter_set_meter_value"
    assert number["step"] >= 0.001  # HA's MQTT number rejects smaller steps
    assert "homeassistant/camera/water_meter/image/config" in svc.mqtt.messages
    drawing = json.loads(svc.mqtt.messages["homeassistant/binary_sensor/water_meter/drawing/config"])
    assert drawing["default_entity_id"] == "binary_sensor.water_meter_drawing"


def test_step_publishes_reading_and_flow(svc):
    s = svc.step(now=1000.0)
    assert s["status"] == "ok" and s["total"] == pytest.approx(705.332, abs=0.002)
    assert json.loads(svc.mqtt.messages["water_meter/state"])["total"] == s["total"]
    assert svc.mqtt.messages["water_meter/image"][:2] == b"\xff\xd8"
    assert svc.step(now=1060.0)["flow"] == 0.0
    assert s["drawing"] is False and "water_meter/draw" not in svc.mqtt.messages


def test_reading_is_timed_at_the_frame_not_the_cycle_start(svc):
    svc.camera.frame_ts = 5000.0
    assert svc.step()["last_valid"] == "1970-01-01T01:23:20+00:00"


def test_water_flow_publishes_draw_start_and_end(svc, monkeypatch):
    base = svc.step(now=1000.0)["total"]
    real = svc.tracker.process
    litres = iter([0, 0, 2.5, 5.0] + [5.0] * 20)

    def process(img, ts):  # the test image never changes: script the meter totals instead
        res = real(img, ts)
        total = round(base + next(litres) / 1000, 4)
        res.reading = dataclasses.replace(res.reading, total=total)
        svc.tracker.state.total, svc.tracker.state.ts = total, ts
        return res

    monkeypatch.setattr(svc.tracker, "process", process)
    drawing = [svc.step(now=1000.0 + 10 * i)["drawing"] for i in range(1, 20)]
    assert drawing[:2] == [False, False] and drawing[2] and not drawing[-1]
    events = [json.loads(p) for topic, p in svc.mqtt.log if topic == "water_meter/draw"]
    assert [e["event"] for e in events] == ["start", "end"]
    assert events[1]["volume_l"] == pytest.approx(5.0) and events[1]["complete"]


def test_camera_error_keeps_last_value(svc):
    total = svc.step(now=1000.0)["total"]
    svc.camera.fail = True
    s = svc.step(now=1030.0)
    assert s["status"] == "camera_error" and s["total"] == total


def test_set_value_via_mqtt(svc):
    svc.step(now=1000.0)
    svc.on_set_value(b"1705.33")
    s = svc.step(now=1030.0)
    assert s["total"] == pytest.approx(1705.332, abs=0.002)
    svc.on_set_value(b"not a number")
    assert svc.pending_value is None


class FakeHA:
    def __init__(self, stats):
        self.stats = stats

    def export_statistics(self):
        return self.stats

    def states(self):
        return {"sensor.usage_tracking_days": "5", "sensor.gas_hot_water_total": "2.5"}

    def hourly_export(self, stat):
        start = dt.datetime(2026, 11, 1)
        return {start + dt.timedelta(hours=h): (0.8 if 11 <= h % 24 < 15 else 0.0) for h in range(10 * 24)}


def test_boiler_sim_publishes_year_estimate(svc):
    s = svc.run_boiler_sim(FakeHA(["sensor.p1_meter_energy_export"]), today=dt.date(2026, 11, 20))
    assert s["status"] == "ok" and s["measured_months"] == 1 and len(s["months"]) == 12
    assert 0 < s["solar_share"] < 100
    assert json.loads(svc.mqtt.messages["water_meter/boiler"])["export_statistic"] == "sensor.p1_meter_energy_export"


def test_boiler_sim_asks_for_statistic_when_ambiguous(svc):
    s = svc.run_boiler_sim(FakeHA(["sensor.a_export", "sensor.b_export"]))
    assert s["status"] == "set export_statistic" and s["solar_share"] is None


def test_boiler_sim_prefers_total_over_tariff_splits(svc):
    stats = ["sensor.p1_meter_energy_export", "sensor.p1_meter_energy_export_tariff_1",
             "sensor.p1_meter_energy_export_tariff_2"]
    s = svc.run_boiler_sim(FakeHA(stats), today=dt.date(2026, 11, 20))
    assert s["export_statistic"] == "sensor.p1_meter_energy_export"


def test_rejected_frames_are_capped(svc):
    svc.step(now=1000.0)
    blank = cv2.imencode(".jpg", 255 * (cv2.imread(str(CFG.parent / "reference" / "ref_mounted.jpg")) * 0 + 1))[1]
    svc.camera.jpeg = blank.tobytes()
    for i in range(4):
        assert svc.step(now=1030.0 + 61 * i)["status"] != "ok"
    assert len(list((svc.share_dir / "rejected").glob("*.jpg"))) <= 4
    assert svc.samples_zip()[:2] == b"PK"
