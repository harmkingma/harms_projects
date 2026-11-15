import pathlib

import cv2
import numpy as np
import pytest

from watermeter.pipeline import MeterReader

CFG = pathlib.Path(__file__).resolve().parents[1] / "meter.yaml"


@pytest.fixture(scope="module")
def reader():
    return MeterReader(CFG)


def test_reference_reading(reader):
    res = reader.read(reader.cfg.reference_image())
    assert res.aligned
    assert res.reading.digits == "00705"
    assert res.reading.status == "ok"
    assert 705.0 <= res.reading.total < 706.0


def test_alignment_recovers_shift_and_rotation(reader):
    ref = reader.cfg.reference_image()
    h, w = ref.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), 6.0, 1.03)
    m[:, 2] += (25, -18)
    moved = cv2.warpAffine(ref, m, (w, h), borderMode=cv2.BORDER_REPLICATE)
    base = reader.read(ref)
    res = reader.read(moved)
    assert res.aligned
    assert res.reading.digits == "00705"
    for a, b in zip(base.dials, res.dials):
        assert abs(((a.value - b.value + 5) % 10) - 5) < 0.1
