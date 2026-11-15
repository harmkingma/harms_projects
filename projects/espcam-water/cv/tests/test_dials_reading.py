import math

import cv2
import numpy as np
import pytest

from watermeter.config import Dial
from watermeter.dials import read_dial
from watermeter.digits import DigitReading
from watermeter.reading import chain_dials, circular_diff, fuse
from watermeter.dials import DialReading


def synthetic_dial(angle_deg: float, size: int = 200, hub: int = 22, tail: int = 55) -> tuple[np.ndarray, Dial]:
    """Light-blue face (like the camera's cast) with a red hub + tapering tail at angle_deg."""
    img = np.full((size, size, 3), (235, 200, 190), np.uint8)
    c = size // 2
    cv2.circle(img, (c, c), 70, (40, 40, 40), 2)
    a = math.radians(angle_deg)
    tip = (c + tail * math.sin(a), c - tail * math.cos(a))
    side = (math.cos(a) * hub * 0.8, math.sin(a) * hub * 0.8)
    tri = np.array([[c + side[0], c + side[1]], [c - side[0], c - side[1]], tip], np.int32)
    cv2.fillPoly(img, [tri], (40, 30, 200))
    cv2.circle(img, (c, c), hub, (40, 30, 200), -1)
    return img, Dial("t", 0.1, c, c, 70)


@pytest.mark.parametrize("angle", [0.0, 3.0, 36.0, 95.0, 180.0, 241.0, 300.0, 357.0])
def test_read_dial_synthetic(angle):
    img, dial = synthetic_dial(angle)
    r = read_dial(img, dial)
    assert abs(circular_diff(r.angle_deg, angle, 360.0)) < 3.0
    assert r.confidence > 0.5


def test_read_dial_offset_pivot():
    # Ring centre estimate 6 px off: the hub-based pivot keeps the angle right.
    img, dial = synthetic_dial(120.0)
    r = read_dial(img, Dial("t", 0.1, dial.cx + 6, dial.cy - 4, dial.r))
    assert abs(circular_diff(r.angle_deg, 120.0, 360.0)) < 3.0


def test_read_dial_no_pointer():
    img = np.full((200, 200, 3), (235, 200, 190), np.uint8)
    r = read_dial(img, Dial("t", 0.1, 100, 100, 70))
    assert math.isnan(r.value) and r.confidence == 0.0


def test_chain_dials_snaps_coarse_to_fine():
    corrected, worst = chain_dials([3.28, 5.94, 8.27, 0.06])
    assert corrected == pytest.approx([3.58006, 5.8006, 8.006, 0.06])
    assert worst == pytest.approx(0.3, abs=0.01)


def test_chain_dials_wraparound():
    # x0.01 just passed 0 while the coarser pointer still looks like 4.98.
    corrected, _ = chain_dials([4.98, 0.1, 1.0, 0.0])
    assert corrected[0] == pytest.approx(5.01)


def test_chain_dials_doubtful_dial_follows_previous():
    # Glare: x0.01 reads 0.9 (really 0.3); previous total 705.4024 -> smallest forward step.
    prior = [4.024, 0.24, 2.4, 4.0]
    corrected, worst = chain_dials([4.03, 0.9, 2.6, 6.0], [True, False, True, True], prior)
    assert corrected == pytest.approx([4.026, 0.26, 2.6, 6.0])
    assert worst < 0.01
    # Without a previous value the doubtful raw value is used and its mismatch counts.
    _, worst = chain_dials([4.03, 0.9, 2.6, 6.0], [True, False, True, True])
    assert worst == pytest.approx(0.36, abs=0.01)


def dr(values):
    return [DialReading(str(i), v, v * 36, (0, 0), 1.0) for i, v in enumerate(values)]


def dg(s):
    return [DigitReading(int(c), 0.1, 0.5) for c in s]


def test_fuse_ok():
    r = fuse(dr([3.58, 5.8, 8.0, 0.06]), dg("00705"))
    assert r.status == "ok" and r.total == pytest.approx(705.358, abs=1e-4)


def test_fuse_tracks_rollover_against_previous():
    # Dial wrapped (0.01 m3) but the last roller still shows 5: continuity says 706.
    r = fuse(dr([0.1, 1.0, 0.0, 0.0]), dg("00705"), previous=705.995, dt_s=60)
    assert r.total == pytest.approx(706.01) and r.status == "ok_tracked"


def test_fuse_rejects_decrease_and_high_flow():
    assert fuse(dr([3.0, 0.0, 0.0, 0.0]), dg("00705"), previous=705.4).status == "implausible"
    assert fuse(dr([5.0, 0.0, 0.0, 0.0]), dg("00705"), previous=705.3, dt_s=60).status == "implausible"


def test_fuse_unreadable_digits_uses_previous():
    digits = [DigitReading(None, float("inf"), 0.0)] * 5
    r = fuse(dr([3.6, 6.0, 0.0, 0.0]), digits, previous=705.35, dt_s=60)
    assert r.status == "ok_tracked" and r.total == pytest.approx(705.36)
