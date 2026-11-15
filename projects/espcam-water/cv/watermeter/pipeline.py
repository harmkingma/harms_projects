"""End-to-end reader: image -> aligned canonical frame -> dials + digits -> fused reading."""
from __future__ import annotations

import dataclasses
import math
import pathlib

import cv2
import numpy as np

from .align import Aligner
from .config import MeterConfig
from .dials import DialReading, read_dial
from .digits import DigitClassifier, DigitReading, crop_digits
from .reading import MIN_DIAL_CONFIDENCE, Reading, fuse


@dataclasses.dataclass
class Result:
    reading: Reading
    dials: list[DialReading]
    digits: list[DigitReading]
    aligned: bool
    inliers: int
    canonical: np.ndarray


class MeterReader:
    def __init__(self, config_path: str | pathlib.Path, *extra_digit_dirs: str | pathlib.Path):
        self.cfg = MeterConfig.load(config_path)
        self.aligner = Aligner(self.cfg)
        # Seed samples ship with the config; learned samples come from the tracker's store.
        self.classifier = DigitClassifier.from_dir(self.cfg.base_dir / "digits", *extra_digit_dirs)

    def read(self, img: np.ndarray, previous: float | None = None, dt_s: float | None = None,
             start_value: float | None = None) -> Result:
        al = self.aligner.align(img)
        dials = [read_dial(al.canonical, d) for d in self.cfg.dials]
        digits = [self.classifier.classify(c) for c in crop_digits(al.canonical, self.cfg.digit_boxes)]
        reading = fuse(dials, digits, previous, dt_s, start_value=start_value) if al.ok else Reading(
            None, None, None, "", [], "no_alignment", f"{al.inliers} inliers")
        return Result(reading, dials, digits, al.ok, al.inliers, al.canonical)

    def annotate(self, res: Result) -> np.ndarray:
        vis = res.canonical.copy()
        for d, r in zip(self.cfg.dials, res.dials):
            ok = not math.isnan(r.value)
            col = (0, 200, 0) if ok and r.confidence >= MIN_DIAL_CONFIDENCE else (0, 0, 255)
            cv2.circle(vis, (int(d.cx), int(d.cy)), int(d.r), col, 2)
            if ok:
                cv2.line(vis, (int(r.pivot[0]), int(r.pivot[1])), (int(r.tip[0]), int(r.tip[1])), (255, 255, 0), 2)
                cv2.putText(vis, f"{r.value:.2f}", (int(d.cx - d.r), int(d.cy + d.r + 18)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
        for (x, y, w, h), r in zip(self.cfg.digit_boxes, res.digits):
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 200, 255), 2)
            txt = "?" if r.digit is None else str(r.digit)
            cv2.putText(vis, txt, (x + 14, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
        rd = res.reading
        line = f"{rd.total:.4f} m3" if rd.total is not None else "--"
        cv2.putText(vis, f"{line}  {rd.status} {rd.detail}", (10, vis.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        return vis
