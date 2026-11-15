"""Roller-digit reading: crop the digit windows and classify them with a nearest-neighbour model.

Training samples live in <digits_dir>/<label>/*.png where label is 0-9. Collect crops with
`python -m watermeter export-digits ...` and sort them into the label folders.
"""
from __future__ import annotations

import dataclasses
import pathlib

import cv2
import numpy as np

SAMPLE_SIZE = (24, 32)  # w, h


@dataclasses.dataclass
class DigitReading:
    digit: int | None
    distance: float        # normalised distance to the nearest sample (lower is better)
    margin: float          # gap to the nearest sample of a different digit (higher is better)


def crop_digits(canonical: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> list[np.ndarray]:
    return [canonical[y:y + h, x:x + w] for x, y, w, h in boxes]


def features(crop: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    small = cv2.resize(gray, SAMPLE_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)
    small -= small.mean()
    norm = np.linalg.norm(small)
    return (small / norm).ravel() if norm > 0 else small.ravel()


class DigitClassifier:
    def __init__(self, samples: list[tuple[int, np.ndarray]]):
        self.labels = np.array([lbl for lbl, _ in samples], dtype=int)
        self.feats = np.stack([features(img) for _, img in samples]) if samples else np.empty((0, 0))

    @classmethod
    def from_dir(cls, *paths: str | pathlib.Path) -> DigitClassifier:
        samples = []
        for path in paths:
            for d in sorted(pathlib.Path(path).glob("[0-9]")):
                for f in sorted(d.glob("*.png")):
                    samples.append((int(d.name), cv2.imread(str(f))))
        return cls(samples)

    @property
    def known_digits(self) -> set[int]:
        return set(self.labels.tolist())

    def count(self, label: int) -> int:
        return int((self.labels == label).sum())

    def distance_to(self, label: int, crop: np.ndarray) -> float:
        """Distance to the nearest sample of `label` (inf if none)."""
        if self.count(label) == 0:
            return float("inf")
        return float(np.linalg.norm(self.feats[self.labels == label] - features(crop), axis=1).min())

    def add(self, label: int, crop: np.ndarray) -> None:
        f = features(crop)[None, :]
        self.feats = f if len(self.labels) == 0 else np.vstack([self.feats, f])
        self.labels = np.append(self.labels, label)

    def classify(self, crop: np.ndarray) -> DigitReading:
        if len(self.labels) == 0:
            return DigitReading(None, float("inf"), 0.0)
        # Unit vectors: squared L2 distance = 2 - 2 * correlation.
        dist = np.linalg.norm(self.feats - features(crop), axis=1)
        i = int(dist.argmin())
        best = int(self.labels[i])
        other = dist[self.labels != best]
        margin = float(other.min() - dist[i]) if other.size else 1.0
        return DigitReading(best, float(dist[i]), margin)
