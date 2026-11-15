import dataclasses
import pathlib

import cv2
import numpy as np
import pytest

from watermeter.digits import DigitClassifier
from watermeter.learning import DigitLearner
from watermeter.pipeline import MeterReader, Result
from watermeter.reading import Reading
from watermeter.tracker import MeterTracker

CFG = pathlib.Path(__file__).resolve().parents[1] / "meter.yaml"


def render(d: str) -> np.ndarray:
    img = np.full((66, 48, 3), 30, np.uint8)
    cv2.putText(img, d, (6, 56), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (230, 230, 230), 4)
    return img


def reading(integer: int, fraction: float, status: str = "ok") -> Reading:
    return Reading(integer + fraction, fraction, integer, "", [], status)


def test_learner_learns_new_digit_only(tmp_path):
    clf = DigitClassifier([(int(c), render(c)) for c in "057"])
    learner = DigitLearner(tmp_path)
    learned = learner.learn(reading(706, 0.4), [render(c) for c in "00706"], clf)
    assert learned == [6]
    assert len(list((tmp_path / "digits" / "6").glob("*.png"))) == 1
    assert 6 in clf.known_digits


def test_learner_skips_rolling_roller(tmp_path):
    clf = DigitClassifier([(int(c), render(c)) for c in "057"])
    assert DigitLearner(tmp_path).learn(reading(706, 0.95), [render(c) for c in "00706"], clf) == []


def test_learner_sends_contradiction_to_review(tmp_path):
    # Tracked value says ...4 but the roller clearly shows a known 5 (e.g. wrong start value).
    clf = DigitClassifier([(int(c), render(c)) for c in "057"])
    learner = DigitLearner(tmp_path)
    assert learner.learn(reading(704, 0.4), [render(c) for c in "00705"], clf) == []
    assert 4 not in clf.known_digits
    assert len(list((tmp_path / "review").glob("*_t4_r5.png"))) == 1


def test_tracker_start_value_and_persistence(tmp_path):
    reader = MeterReader(CFG)
    state = tmp_path / "state.json"
    tr = MeterTracker(reader, state, DigitLearner(tmp_path / "store"))
    assert tr.apply_start_value(705.33, ts=1000.0)
    res = tr.process(reader.cfg.reference_image(), ts=1060.0)
    assert res.reading.total == pytest.approx(705.332, abs=0.002)
    tr2 = MeterTracker(reader, state)
    assert tr2.state.total == pytest.approx(res.reading.total)
    assert not tr2.apply_start_value(705.33)       # unchanged option is not re-applied
    assert tr2.apply_start_value(710.0)


def test_tracker_approximate_start_value_is_not_rejected(tmp_path):
    # Entered value slightly above the dials (705.34 vs 705.332) and read right away.
    reader = MeterReader(CFG)
    tr = MeterTracker(reader, tmp_path / "s.json")
    tr.apply_start_value(705.34, ts=1000.0)
    res = tr.process(reader.cfg.reference_image(), ts=1000.5)
    assert res.reading.total == pytest.approx(705.332, abs=0.002)
    assert not tr.state.pending_start


@dataclasses.dataclass
class FakeCfg:
    digit_boxes: list = dataclasses.field(default_factory=list)


class FakeReader:
    """Always reads fraction 0.5 with the rollers showing `digits_integer`."""
    def __init__(self, digits_integer):
        self.digits_integer = digits_integer
        self.classifier = DigitClassifier([(d, render(str(d))) for d in range(10)])
        self.cfg = FakeCfg()

    def read(self, img, previous=None, dt_s=None, start_value=None):
        integer = int(start_value if start_value is not None else previous)
        rd = Reading(integer + 0.5, 0.5, integer, str(self.digits_integer), [], "ok_tracked",
                     digits_integer=self.digits_integer)
        return Result(rd, [], [], False, 0, img)


def test_tracker_resyncs_to_digits_after_consistent_conflicts(tmp_path):
    tr = MeterTracker(FakeReader(712), tmp_path / "s.json", resync_after=3)
    tr.apply_start_value(710.4, ts=0.0)
    statuses = [tr.process(np.zeros((1, 1, 3), np.uint8), ts=60.0 * i).reading.status for i in range(1, 4)]
    assert statuses == ["ok_tracked", "ok_tracked", "resynced"]
    assert tr.state.total == pytest.approx(712.5)
