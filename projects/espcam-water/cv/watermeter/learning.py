"""Self-learning of roller digits: label crops from the tracked meter value and store them.

Storage layout (all plain files, so it can be browsed/downloaded via the Samba share):
  <root>/digits/<0-9>/<timestamp>_p<pos>.png   learned samples, used by the classifier
  <root>/review/<timestamp>_p<pos>_t<label>_r<read>.png   crops that contradicted the tracked value
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import pathlib

import cv2
import numpy as np

from .digits import DigitClassifier
from .reading import Reading


@dataclasses.dataclass
class LearnConfig:
    max_per_label: int = 20
    min_novelty: float = 0.08      # skip crops this close to an existing sample of the same digit
    conflict_distance: float = 0.5  # a crop this close to another known digit is suspicious
    frac_window: tuple[float, float] = (0.15, 0.85)  # last roller is centred on a digit here
    max_review: int = 300


class DigitLearner:
    def __init__(self, root: str | pathlib.Path, cfg: LearnConfig | None = None):
        self.root = pathlib.Path(root)
        self.digits_dir = self.root / "digits"
        self.review_dir = self.root / "review"
        self.cfg = cfg or LearnConfig()
        self.digits_dir.mkdir(parents=True, exist_ok=True)
        self.review_dir.mkdir(parents=True, exist_ok=True)

    def learn(self, reading: Reading, crops: list[np.ndarray], clf: DigitClassifier,
              when: dt.datetime | None = None) -> list[int]:
        """Add crops whose label follows from a trusted reading. Returns the learned labels."""
        if reading.total is None or reading.integer is None or reading.fraction is None:
            return []
        lo, hi = self.cfg.frac_window
        if not lo <= reading.fraction <= hi:
            return []
        stamp = (when or dt.datetime.now()).strftime("%Y%m%d_%H%M%S")
        labels = [int(c) for c in str(reading.integer).zfill(len(crops))[-len(crops):]]
        learned = []
        for pos, (label, crop) in enumerate(zip(labels, crops)):
            guess = clf.classify(crop)
            if (guess.digit is not None and guess.digit != label
                    and guess.distance < self.cfg.conflict_distance
                    and guess.distance < clf.distance_to(label, crop)):
                self._review(crop, stamp, pos, label, guess.digit)
                continue
            if clf.count(label) >= self.cfg.max_per_label:
                continue
            if clf.distance_to(label, crop) < self.cfg.min_novelty:
                continue
            d = self.digits_dir / str(label)
            d.mkdir(exist_ok=True)
            cv2.imwrite(str(d / f"{stamp}_p{pos}.png"), crop)
            clf.add(label, crop)
            learned.append(label)
        return learned

    def _review(self, crop: np.ndarray, stamp: str, pos: int, label: int, read: int) -> None:
        files = sorted(self.review_dir.glob("*.png"))
        for old in files[: max(0, len(files) - self.cfg.max_review + 1)]:
            old.unlink()
        cv2.imwrite(str(self.review_dir / f"{stamp}_p{pos}_t{label}_r{read}.png"), crop)
