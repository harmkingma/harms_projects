"""Debug: dump redness map and canonical crop for each dial of one image (side by side)."""
import sys

import cv2
import numpy as np

from watermeter.dials import redness
from watermeter.pipeline import MeterReader

reader = MeterReader(sys.argv[2] if len(sys.argv) > 2 else "cv/meter.yaml")
al = reader.aligner.align(cv2.imread(sys.argv[1]))
tiles = []
for d in reader.cfg.dials:
    x0, y0, r = int(d.cx - d.r), int(d.cy - d.r), int(d.r)
    crop = al.canonical[y0:y0 + 2 * r, x0:x0 + 2 * r]
    red = cv2.cvtColor(cv2.normalize(redness(crop), None, 0, 255, cv2.NORM_MINMAX), cv2.COLOR_GRAY2BGR)
    tiles.append(np.vstack([cv2.resize(crop, (200, 200)), cv2.resize(red, (200, 200))]))
cv2.imwrite("dataset/debug/dials.png", np.hstack(tiles))
