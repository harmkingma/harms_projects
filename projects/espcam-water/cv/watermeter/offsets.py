"""Fit per-dial zero offsets from images taken while water flows.

Each coarse dial must agree with its finer neighbour (frac(coarse) == fine / 10). The median
disagreement over many pointer positions is a fixed per-dial offset (printing/parallax/pivot);
it is folded into `zero_deg`. The finest dial is the reference (its own offset only shifts the
total by < 0.01 L).

Usage: python -m watermeter.offsets IMAGES_OR_DIRS --config cv/meter.yaml [--write]
"""
from __future__ import annotations

import argparse

import cv2
import numpy as np

from .config import MeterConfig
from .pipeline import MeterReader
from .reading import MIN_DIAL_CONFIDENCE, circular_diff

MIN_FRAMES = 30
MIN_FINE_COVERAGE = 6   # distinct integer positions the finer dial must visit


def fit(raw: np.ndarray) -> tuple[list[float], list[float]]:
    """raw: (frames, dials) coarse -> fine. Returns offsets (dial units) and residual spread (p95 |r|)."""
    n = raw.shape[1]
    offsets, spread = [0.0] * n, [0.0] * n
    for i in range(n - 2, -1, -1):
        frac = raw[:, i + 1] / 10
        r = np.array([circular_diff(c, round(c - f) + f) for c, f in zip(raw[:, i], frac)])
        med = float(np.median(r))
        offsets[i] = med + offsets[i + 1] / 10
        spread[i] = float(np.percentile(np.abs(r - med), 95))
    return offsets, spread


def main() -> None:
    from .__main__ import image_paths

    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+", help="image files and/or directories (taken while water flows)")
    ap.add_argument("--config", default="cv/meter.yaml")
    ap.add_argument("--write", action="store_true", help="add the fitted offsets to zero_deg in the config")
    args = ap.parse_args()

    reader = MeterReader(args.config)
    rows = []
    for path in image_paths(args.images):
        res = reader.read(cv2.imread(str(path)))
        values = [d.value for d in res.dials]
        if res.aligned and all(d.confidence >= MIN_DIAL_CONFIDENCE for d in res.dials):
            rows.append(values)
    raw = np.array(rows)
    if len(raw) < MIN_FRAMES:
        raise SystemExit(f"only {len(raw)} usable frames; need {MIN_FRAMES}")
    for i in range(raw.shape[1] - 1):
        covered = len(set(np.floor(raw[:, i + 1]).astype(int)))
        if covered < MIN_FINE_COVERAGE:
            raise SystemExit(f"{reader.cfg.dials[i + 1].name} only visited {covered} positions; run more water")

    offsets, spread = fit(raw)
    cfg = MeterConfig.load(args.config)
    for d, o, s in zip(cfg.dials, offsets, spread):
        print(f"{d.name:8s} offset {o:+.3f} units ({o * 36:+.1f} deg), residual p95 {s:.3f}, "
              f"zero_deg {d.zero_deg:.1f} -> {d.zero_deg + o * 36:.1f}")
        d.zero_deg = round(d.zero_deg + o * 36, 1)
    print(f"{len(raw)} frames")
    if args.write:
        cfg.save(args.config)
        print(f"written to {args.config}")


if __name__ == "__main__":
    main()
