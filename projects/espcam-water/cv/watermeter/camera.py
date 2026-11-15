"""Snapshot capture from the ESPHome meter camera with the flash LED on."""
from __future__ import annotations

import time
import urllib.parse
import urllib.request

import cv2
import numpy as np


class Camera:
    def __init__(self, host: str, brightness: int = 140, settle: float = 1.5, min_mean: float = 40,
                 retries: int = 4, timeout: float = 15):
        self.light_url = f"http://{host}/light/{urllib.parse.quote('Flash LED')}"
        self.snapshot_url = f"http://{host}:8081/"
        self.brightness, self.settle, self.min_mean = brightness, settle, min_mean
        self.retries, self.timeout = retries, timeout
        self.frame_ts: float | None = None  # when the last returned frame was requested

    def _post(self, url: str) -> None:
        urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=10).close()

    def _fetch(self) -> bytes:
        with urllib.request.urlopen(self.snapshot_url, timeout=self.timeout) as resp:
            return resp.read()

    @staticmethod
    def mean_level(data: bytes) -> float:
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_REDUCED_GRAYSCALE_8)
        return float(img.mean()) if img is not None else 0.0

    def _snapshot(self) -> bytes:
        # Both frame buffers (frame_buffer_count: 2) may hold frames exposed before the flash.
        for _ in range(2):
            self._fetch()
        for _ in range(self.retries):
            # The buffers are drained, so the camera exposes this frame right after the request.
            ts = time.time()
            data = self._fetch()
            if self.brightness == 0 or self.mean_level(data) >= self.min_mean:
                self.frame_ts = ts
                return data
            time.sleep(0.5)
        raise RuntimeError(f"frames still dark after {self.retries} retries")

    def capture(self) -> bytes:
        """JPEG bytes of one lit frame. Raises on network errors or persistently dark frames."""
        try:
            if self.brightness > 0:
                self._post(f"{self.light_url}/turn_on?brightness={self.brightness}")
                time.sleep(self.settle)
            return self._snapshot()
        finally:
            if self.brightness > 0:
                self._post(f"{self.light_url}/turn_off")
