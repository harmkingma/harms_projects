"""Create meter.yaml from a reference image: finds the meter glass and the four dials.

Usage: python -m watermeter.calibrate REF.jpg --rotation 7 --out cv/meter.yaml
Digit boxes are kept from an existing config (or left empty) and must be checked on the
written canonical preview (<out>.canonical.png).
"""
from __future__ import annotations

import argparse
import math
import os
import pathlib

import cv2
import numpy as np

from .config import Dial, MeterConfig

# Clockwise order around the meter centre, starting at 12 o'clock.
DIAL_ORDER = [("x0.1", 0.1), ("x0.01", 0.01), ("x0.001", 0.001), ("x0.0001", 0.0001)]


def find_meter(gray: np.ndarray) -> tuple[float, float, float]:
    c = cv2.HoughCircles(cv2.medianBlur(gray, 9), cv2.HOUGH_GRADIENT, dp=2, minDist=500,
                         param1=100, param2=60, minRadius=250, maxRadius=450)
    if c is None:
        raise RuntimeError("meter glass not found")
    x, y, r = c[0][0]
    return float(x), float(y), float(r)


def find_dials(gray: np.ndarray, meter: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    mx, my, mr = meter
    c = cv2.HoughCircles(cv2.medianBlur(gray, 5), cv2.HOUGH_GRADIENT, dp=1.2, minDist=90,
                         param1=120, param2=40, minRadius=int(mr * 0.16), maxRadius=int(mr * 0.29))
    if c is None:
        raise RuntimeError("no dials found")
    inside = [tuple(map(float, d)) for d in c[0] if math.hypot(d[0] - mx, d[1] - my) < mr * 0.95]
    if len(inside) < 4:
        raise RuntimeError(f"expected 4 dials, found {len(inside)}")
    return inside[:4]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("reference")
    ap.add_argument("--rotation", type=float, default=0.0, help="meter tilt, clockwise degrees")
    ap.add_argument("--out", default="cv/meter.yaml")
    args = ap.parse_args()

    img = cv2.imread(args.reference)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    meter = find_meter(gray)
    dials_ref = find_dials(gray, meter)
    out = pathlib.Path(args.out)
    size = int(2 * (meter[2] + 30))
    old_boxes = MeterConfig.load(out).digit_boxes if out.exists() else []
    cfg = MeterConfig(
        reference=os.path.relpath(args.reference, out.parent).replace("\\", "/"),
        ref_center=(meter[0], meter[1]), ref_radius=meter[2], rotation_deg=args.rotation,
        size=size, dials=[], digit_boxes=old_boxes, base_dir=out.parent)
    t = cfg.ref_to_canonical()
    canon = []
    for x, y, r in dials_ref:
        p = t @ np.array([x, y, 1.0])
        bearing = math.degrees(math.atan2(p[0] - size / 2, -(p[1] - size / 2))) % 360
        canon.append((bearing, float(p[0]), float(p[1]), r))
    canon.sort()
    cfg.dials = [Dial(name, factor, round(x, 1), round(y, 1), round(r, 1))
                 for (name, factor), (_, x, y, r) in zip(DIAL_ORDER, canon)]
    cfg.save(out)

    preview = cv2.warpAffine(img, t[:2], (size, size))
    for d in cfg.dials:
        cv2.circle(preview, (int(d.cx), int(d.cy)), int(d.r), (0, 255, 0), 2)
        cv2.putText(preview, d.name, (int(d.cx - d.r), int(d.cy - d.r - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    for x, y, w, h in cfg.digit_boxes:
        cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 200, 255), 2)
    for gy in range(0, size, 50):
        cv2.line(preview, (0, gy), (8, gy), (0, 0, 255), 1)
        cv2.putText(preview, str(gy), (10, gy + 4), cv2.FONT_HERSHEY_PLAIN, 0.8, (0, 0, 255), 1)
    for gx in range(0, size, 50):
        cv2.line(preview, (gx, 0), (gx, 8), (0, 0, 255), 1)
        cv2.putText(preview, str(gx), (gx - 8, 20), cv2.FONT_HERSHEY_PLAIN, 0.8, (0, 0, 255), 1)
    cv2.imwrite(str(out.with_suffix(".canonical.png")), preview)
    print(f"meter {meter}, size {size}")
    for d in cfg.dials:
        print(d)


if __name__ == "__main__":
    main()
