"""Meter layout configuration (canonical, upright meter frame) and reference-image calibration."""
from __future__ import annotations

import dataclasses
import pathlib

import cv2
import numpy as np
import yaml


@dataclasses.dataclass
class Dial:
    name: str
    factor: float          # m3 per full revolution / 10, e.g. 0.1 for the x0.1 dial
    cx: float
    cy: float
    r: float
    zero_deg: float = 0.0  # extra per-dial correction of the "0" direction, clockwise


@dataclasses.dataclass
class MeterConfig:
    reference: str                     # reference image path (relative to the config file)
    ref_center: tuple[float, float]    # meter glass centre in the reference image
    ref_radius: float
    rotation_deg: float                # meter "up" in the reference image, clockwise from image up
    size: int                          # canonical frame is size x size, meter centre in the middle
    dials: list[Dial]
    digit_boxes: list[tuple[int, int, int, int]]  # x, y, w, h in the canonical frame, most significant first
    base_dir: pathlib.Path = dataclasses.field(default=pathlib.Path("."), repr=False)

    @classmethod
    def load(cls, path: str | pathlib.Path) -> MeterConfig:
        path = pathlib.Path(path)
        data = yaml.safe_load(path.read_text())
        data["dials"] = [Dial(**d) for d in data["dials"]]
        data["digit_boxes"] = [tuple(b) for b in data["digit_boxes"]]
        data["ref_center"] = tuple(data["ref_center"])
        return cls(**data, base_dir=path.parent)

    def save(self, path: str | pathlib.Path) -> None:
        data = dataclasses.asdict(self)
        data.pop("base_dir")
        data["ref_center"] = list(data["ref_center"])
        data["digit_boxes"] = [list(b) for b in data["digit_boxes"]]
        pathlib.Path(path).write_text(yaml.safe_dump(data, sort_keys=False))

    def reference_image(self) -> np.ndarray:
        img = cv2.imread(str(self.base_dir / self.reference))
        if img is None:
            raise FileNotFoundError(self.base_dir / self.reference)
        return img

    def ref_to_canonical(self) -> np.ndarray:
        """3x3 transform from reference-image pixels to the upright canonical frame."""
        cx, cy = self.ref_center
        m = cv2.getRotationMatrix2D((cx, cy), self.rotation_deg, 1.0)
        m[0, 2] += self.size / 2 - cx
        m[1, 2] += self.size / 2 - cy
        return np.vstack([m, [0, 0, 1]])
