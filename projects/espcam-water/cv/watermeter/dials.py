"""Read a red-pointer dial: angle of the pointer tip around the dial centre -> value 0..10."""
from __future__ import annotations

import dataclasses
import math

import cv2
import numpy as np

from .config import Dial


@dataclasses.dataclass
class DialReading:
    name: str
    value: float          # 0 <= value < 10
    angle_deg: float      # clockwise from the dial's "0"
    tip: tuple[float, float]
    confidence: float     # 0..1
    pivot: tuple[float, float] = (0.0, 0.0)


def redness(bgr: np.ndarray) -> np.ndarray:
    """Red minus the strongest other channel; robust to the camera's blue/purple cast."""
    b, g, r = cv2.split(bgr.astype(np.int16))
    return np.clip(r - np.maximum(g, b), 0, 255).astype(np.uint8)


def read_dial(canonical: np.ndarray, dial: Dial) -> DialReading:
    cx, cy, r = dial.cx, dial.cy, dial.r
    x0, y0 = int(cx - r), int(cy - r)
    roi = canonical[max(y0, 0):int(cy + r), max(x0, 0):int(cx + r)]
    red = redness(roi)
    yy, xx = np.mgrid[0:roi.shape[0], 0:roi.shape[1]]
    dx = xx + max(x0, 0) - cx
    dy = yy + max(y0, 0) - cy
    dist = np.hypot(dx, dy)
    inside = dist < 0.92 * r
    vals = red[inside]
    if vals.size == 0 or vals.max() < 20:
        return DialReading(dial.name, float("nan"), float("nan"), (cx, cy), 0.0)
    thr, _ = cv2.threshold(vals.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thr = max(thr, 20)
    strong = (red > thr) & inside
    # Hysteresis: glare washes out parts of the pointer, so grow the strong core into weaker red.
    weak = ((red > 0.45 * thr) & inside).astype(np.uint8)
    weak = cv2.morphologyEx(weak, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(weak)
    if n <= 1:
        return DialReading(dial.name, float("nan"), float("nan"), (cx, cy), 0.0)
    # The pointer is the red component that covers the hub (closest to the centre).
    best, best_d = 0, 1e9
    for i in range(1, n):
        sel = labels == i
        if stats[i, cv2.CC_STAT_AREA] < 0.01 * r * r or not strong[sel].any():
            continue
        d = dist[sel].min()
        if d < best_d:
            best, best_d = i, d
    if best == 0 or best_d > 0.35 * r:
        return DialReading(dial.name, float("nan"), float("nan"), (cx, cy), 0.0)
    comp = (labels == best).astype(np.uint8)
    # Pointer = round hub on the pivot + tapering tail. The hub centre (deepest point of the
    # distance transform) is a better pivot than the dial ring centre, which perspective shifts.
    dt = cv2.distanceTransform(comp, cv2.DIST_L2, 5)
    hy, hx = np.unravel_index(int(dt.argmax()), dt.shape)
    hub_r = float(dt.max())
    px, py = hx + max(x0, 0), hy + max(y0, 0)
    sel = comp.astype(bool)
    tx = xx[sel] + max(x0, 0) - px
    ty = yy[sel] + max(y0, 0) - py
    td = np.hypot(tx, ty)
    reach = float(td.max())
    far = td > max(0.75 * reach, hub_r * 1.2)
    if far.sum() < 3:
        return DialReading(dial.name, float("nan"), float("nan"), (px, py), 0.0)
    wx, wy = tx[far].mean(), ty[far].mean()
    bearing = math.atan2(wx, -wy)
    angle = (math.degrees(bearing) - dial.zero_deg) % 360.0
    tip = (px + reach * math.sin(bearing), py - reach * math.cos(bearing))
    # A clean tail is long relative to the hub and its distal pixels share one bearing.
    spread = float(np.abs(np.angle(np.exp(1j * (np.arctan2(tx[far], -ty[far]) - bearing)))).mean())
    tail = reach / max(hub_r, 1.0)
    confidence = float(np.clip(min((tail - 1.3) / 0.7, 1.0) * (1.0 - spread / 0.5), 0.0, 1.0))
    return DialReading(dial.name, angle / 36.0 % 10.0, angle, tip, confidence, (float(px), float(py)))
