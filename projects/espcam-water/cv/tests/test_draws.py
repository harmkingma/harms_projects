import datetime as dt

import pytest

from watermeter.__main__ import load_readings
from watermeter.draws import DrawDetector, analyse


def water(t, segs):
    """Litres used up to t for (start, end, L/min) segments."""
    return sum(max(0.0, min(t, e) - s) * q / 60 for s, e, q in segs if t > s)


def readings(segs, times):
    # m3 at 4 decimals (0.1 L), like the reader
    return [(t, round(water(t, segs) / 1000, 4)) for t in times]


def run(det, pts):
    events = []
    for t, v in pts:
        events += det.add(t, v)
    return events


def test_start_and_stop_are_placed_inside_the_interval():
    pts = readings([(1012, 1500, 7.5)], range(960, 1700, 30))
    d = analyse(pts)
    assert d.start == pytest.approx(1012, abs=1) and d.end == pytest.approx(1500, abs=1)
    assert d.flowing_s == pytest.approx(488, abs=2)
    assert d.payload()["main_flow"] == pytest.approx(7.5, abs=0.05)


def test_pause_does_not_count_as_running_time():
    pts = readings([(1000, 1300, 10.0), (1390, 1600, 10.0)], range(985, 1800, 10))
    d = analyse(pts)
    assert d.flowing_s == pytest.approx(510, abs=3)
    assert d.end - d.start == pytest.approx(600, abs=3)


def test_flow_change_without_pause_is_all_running_time():
    # rain head 14 L/min, then the hand shower at 9 L/min
    d = analyse(readings([(1000, 1240, 14.0), (1240, 1480, 9.0)], range(985, 1700, 10)))
    assert d.main_flowing_s == pytest.approx(480, abs=3)
    assert d.main_volume_l == pytest.approx(92, abs=0.2)


def test_low_flow_end_of_the_shower_itself_is_not_cut_off():
    # hand shower at 5 L/min (below half the rain head's 14) right after, no pause
    p = analyse(readings([(1000, 1300, 14.0), (1300, 1420, 5.0)], range(985, 1700, 10))).payload()
    assert p["main_volume_l"] == pytest.approx(80, abs=0.2) and p["side_volume_l"] == 0


def test_washbasin_after_the_shower_is_side_water():
    p = analyse(readings([(1000, 1480, 7.5), (1530, 1590, 3.0)], range(985, 1800, 10))).payload()
    assert p["main_volume_l"] == pytest.approx(60, abs=0.2)
    assert p["side_volume_l"] == pytest.approx(3, abs=0.2)
    assert p["main_flow"] == pytest.approx(7.5, abs=0.1)
    assert p["volume_l"] == pytest.approx(63, abs=0.2)


def test_start_transient_does_not_shorten_the_run():
    # 2026-11-05 06:30 shower, one reading per minute, then the washbasin.
    hms = ["06:29:02", "06:30:05", "06:31:07", "06:32:10", "06:33:13", "06:34:16", "06:35:22", "06:36:25",
           "06:37:27", "06:38:30", "06:39:33", "06:40:35", "06:41:38", "06:42:41", "06:43:44", "06:44:47",
           "06:45:49", "06:46:52", "06:47:55", "06:48:58", "06:50:01", "06:51:03", "06:52:06", "06:53:09",
           "06:54:12", "06:55:15", "06:56:17"]
    totals = [705.4384, 705.4384, 705.4439, 705.4543, 705.4622, 705.4700, 705.4781, 705.4863, 705.4939,
              705.5013, 705.5088, 705.5166, 705.5243, 705.5319, 705.5396, 705.5473, 705.5549, 705.5626,
              705.5703, 705.5773, 705.5773, 705.5791, 705.5792, 705.5795, 705.5799, 705.5799, 705.5799]
    secs = [int(h) * 3600 + int(m) * 60 + int(s) for h, m, s in (x.split(":") for x in hms)]
    p = analyse(list(zip(secs, totals))).payload()
    assert p["volume_l"] == pytest.approx(141.5, abs=0.05)
    assert p["main_volume_l"] == pytest.approx(138.9, abs=0.05) and p["side_volume_l"] == pytest.approx(2.6)
    # The old start-to-dry-reading timing gave 24.1 min and 5.9 L/min for this draw.
    assert p["main_flowing_min"] == pytest.approx(p["main_duration_min"], abs=0.05)
    assert 7.4 < p["main_flow"] < 7.8


def test_reading_gap_marks_the_draw_incomplete():
    d = analyse([(1000, 1.0), (1030, 1.0), (1630, 1.05), (1640, 1.0517), (1650, 1.0517)])
    assert not d.complete and d.volume_l == pytest.approx(51.7)


def test_detector_keeps_a_short_pause_in_one_draw():
    det = DrawDetector(gap_s=120)
    events = run(det, readings([(1005, 1100, 6.0), (1150, 1200, 6.0)], range(960, 1500, 10)))
    assert [e["event"] for e in events] == ["start", "end"] and not det.open
    assert events[1]["volume_l"] == pytest.approx(14.5, abs=0.2)
    assert events[1]["flowing_min"] == pytest.approx(145 / 60, abs=0.05)


def test_detector_splits_draws_on_the_gap():
    events = run(DrawDetector(gap_s=120), readings([(1005, 1100, 6.0), (1300, 1350, 6.0)], range(960, 1600, 10)))
    assert [e["event"] for e in events] == ["start", "end", "start", "end"]


def test_open_draw_survives_a_restart(tmp_path):
    path = tmp_path / "draw.json"
    pts = readings([(1005, 1400, 6.0)], range(960, 1700, 10))
    events = run(DrawDetector(120, path=path), pts[:20])
    det = DrawDetector(120, path=path)
    assert det.open
    events += run(det, pts[20:])
    assert [e["event"] for e in events] == ["start", "end"]
    assert events[-1]["volume_l"] == pytest.approx(39.5, abs=0.2)


def test_set_meter_value_ends_the_draw_without_counting_the_jump():
    det = DrawDetector(120)
    run(det, readings([(1005, 1100, 6.0)], range(960, 1060, 10)))
    assert det.open
    events = det.reset(1070, 500.0)
    assert [e["event"] for e in events] == ["end"] and not det.open
    assert det.add(1080, 500.0) == [] and not det.open


def test_ha_history_csv_gets_its_unchanged_readings_back(tmp_path):
    # HA stores only changes; a 7.5 L/min shower read every 30 s, starting 12 s before a reading.
    t0 = dt.datetime(2026, 11, 7, 6, 0, tzinfo=dt.timezone.utc).timestamp()
    pts = readings([(t0 + 1008, t0 + 1500, 7.5)], [t0 + s for s in range(0, 2400, 30)])
    rows = ["entity_id,state,last_changed", f"sensor.water_meter_total,unavailable,{iso_z(t0 - 60)}"]
    rows += [f"sensor.water_meter_total,{v},{iso_z(t)}" for i, (t, v) in enumerate(pts) if i == 0 or v != pts[i - 1][1]]
    csv_path = tmp_path / "history.csv"
    csv_path.write_text("\n".join(rows))
    p = analyse(load_readings(csv_path, 30)).payload()
    assert p["main_volume_l"] == pytest.approx(61.5, abs=0.1)
    assert p["main_flowing_min"] == pytest.approx(492 / 60, abs=0.05)
    assert p["main_flow"] == pytest.approx(7.5, abs=0.1)


def iso_z(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
