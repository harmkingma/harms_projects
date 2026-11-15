"""Register a camera image onto the reference image and warp it into the canonical meter frame."""
from __future__ import annotations

import dataclasses

import cv2
import numpy as np

from .config import MeterConfig


@dataclasses.dataclass
class Alignment:
    canonical: np.ndarray     # BGR image in the canonical frame
    transform: np.ndarray     # 3x3, input pixels -> canonical
    inliers: int
    ok: bool


class Aligner:
    def __init__(self, cfg: MeterConfig, n_features: int = 4000, min_inliers: int = 40):
        self.cfg = cfg
        self.min_inliers = min_inliers
        self.orb = cv2.ORB_create(n_features)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        ref = cv2.cvtColor(cfg.reference_image(), cv2.COLOR_BGR2GRAY)
        mask = np.zeros_like(ref)
        cx, cy = cfg.ref_center
        # Include the meter ring: it has more texture than the white dial face.
        cv2.circle(mask, (int(cx), int(cy)), int(cfg.ref_radius * 1.35), 255, -1)
        self.ref_kp, self.ref_desc = self.orb.detectAndCompute(self._prep(ref), mask)
        self.ref_to_canon = cfg.ref_to_canonical()

    @staticmethod
    def _prep(gray: np.ndarray) -> np.ndarray:
        return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

    def align(self, img: np.ndarray) -> Alignment:
        gray = self._prep(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        kp, desc = self.orb.detectAndCompute(gray, None)
        h = None
        inliers = 0
        if desc is not None and len(kp) >= 10:
            pairs = self.matcher.knnMatch(desc, self.ref_desc, k=2)
            good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
            if len(good) >= 10:
                src = np.float32([kp[m.queryIdx].pt for m in good])
                dst = np.float32([self.ref_kp[m.trainIdx].pt for m in good])
                h, inl = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
                inliers = int(inl.sum()) if inl is not None else 0
        ok = h is not None and inliers >= self.min_inliers
        if not ok:
            h = np.eye(3)
        t = self.ref_to_canon @ h
        size = self.cfg.size
        canonical = cv2.warpPerspective(img, t, (size, size), flags=cv2.INTER_LINEAR)
        return Alignment(canonical, t, inliers, ok)
