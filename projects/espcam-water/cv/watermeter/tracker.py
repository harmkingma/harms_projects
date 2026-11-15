"""Stateful meter tracking: start value, persistence, digit cross-check/resync and self-learning."""
from __future__ import annotations

import dataclasses
import json
import math
import pathlib
import time

import numpy as np

from .digits import crop_digits
from .learning import DigitLearner
from .pipeline import MeterReader, Result

ALL_DIGITS = set(range(10))


@dataclasses.dataclass
class TrackerState:
    total: float | None = None
    ts: float | None = None
    start_value: float | None = None   # last applied start value, so a changed option is re-applied
    conflicts: int = 0
    pending_start: bool = False        # next reading is anchored to the start value


class MeterTracker:
    def __init__(self, reader: MeterReader, state_path: str | pathlib.Path,
                 learner: DigitLearner | None = None, resync_after: int = 5):
        self.reader = reader
        self.learner = learner
        self.resync_after = resync_after
        self.state_path = pathlib.Path(state_path)
        self.state = TrackerState()
        if self.state_path.exists():
            self.state = TrackerState(**json.loads(self.state_path.read_text()))

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(dataclasses.asdict(self.state)))
        for attempt in range(5):
            try:
                tmp.replace(self.state_path)
                return
            except PermissionError:  # Windows: scanner/indexer briefly holds the target
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))

    def apply_start_value(self, value: float | None, ts: float | None = None, force: bool = False) -> bool:
        """Set the meter value (m3) if it differs from the last applied start value (or force)."""
        if value is None or (value == self.state.start_value and not force):
            return False
        self.state = TrackerState(total=float(value), ts=ts or time.time(), start_value=float(value),
                                  pending_start=True)
        self._save()
        return True

    def process(self, img: np.ndarray, ts: float | None = None) -> Result:
        ts = ts or time.time()
        prev, prev_ts = self.state.total, self.state.ts
        if self.state.pending_start:
            res = self.reader.read(img, start_value=self.state.start_value)
        else:
            res = self.reader.read(img, prev, (ts - prev_ts) if prev_ts else None)
        rd = res.reading

        # Rollers are trusted for a resync only once every digit has been learned, and only
        # after several consistent readings: catches m3 wraps missed while the reader was down.
        digits_trusted = self.reader.classifier.known_digits >= ALL_DIGITS
        if (rd.fraction is not None and rd.digits_integer is not None and rd.integer is not None
                and rd.digits_integer != rd.integer and digits_trusted):
            self.state.conflicts += 1
            if self.state.conflicts >= self.resync_after:
                rd.integer = rd.digits_integer
                rd.total = round(rd.digits_integer + rd.fraction, 4)
                rd.status, rd.detail = "resynced", f"adopted digits {rd.digits_integer}"
                self.state.conflicts = 0
        elif rd.total is not None:
            self.state.conflicts = 0

        if rd.total is not None and not math.isnan(rd.total):
            self.state.total, self.state.ts = rd.total, ts
            self.state.pending_start = False
            self._save()
            if self.learner and res.aligned:
                crops = crop_digits(res.canonical, self.reader.cfg.digit_boxes)
                learned = self.learner.learn(rd, crops, self.reader.classifier)
                if learned:
                    rd.detail = (rd.detail + f" learned {''.join(map(str, learned))}").strip()
        return res
