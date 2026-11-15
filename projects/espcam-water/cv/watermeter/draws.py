"""Water draws from meter readings: start/stop inside a sampling interval, pauses and the main run.

A reading only tells how much water passed since the previous one. While a shower or tap runs, its
flow is nearly constant, so an interval holding less water than the one next to it was only partly
on: on-time = litres / neighbour flow. That places start and stop inside the interval instead of on
the reading times (up to a whole interval off each), and pauses do not count as running time.

The main run is the part of a draw at its main flow level (the level that carries most of the
water, e.g. the shower itself). Use before or after it that is separated by a dry reading and
stays below half that level, such as the washbasin after a shower, is reported as side water.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pathlib

MAIN_LEVEL = 0.5  # a wet stretch reaching this fraction of the main flow level belongs to the main run
FULL = 0.8        # an inner interval at >= this fraction of its neighbours' flow ran all the time
RESOLUTION_L = 0.1  # meter total resolution (4 decimals in m3)


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


@dataclasses.dataclass
class Interval:
    t0: float
    t1: float
    litres: float

    @property
    def seconds(self) -> float:
        return self.t1 - self.t0

    @property
    def lpm(self) -> float:
        return self.litres * 60 / self.seconds if self.seconds > 0 else 0.0


def on_times(ivs: list[Interval]) -> list[float]:
    """Seconds each interval had water running. Intervals outside `ivs` count as dry."""
    out = []
    for i, iv in enumerate(ivs):
        if iv.litres <= 0:
            out.append(0.0)
            continue
        nbs = [n.lpm for n in ivs[max(i - 1, 0):i] + ivs[i + 1:i + 2] if n.litres > 0]
        if len(nbs) == 2:
            # Inner: ran all the time unless it dips below both neighbours (a pause inside it).
            ref = min(nbs)
            full = iv.litres >= FULL * ref * iv.seconds / 60 - RESOLUTION_L
            out.append(iv.seconds if full else iv.litres * 60 / ref)
        else:
            # Start or stop inside this interval, at the flow of the interval next to it.
            out.append(min(iv.seconds, iv.litres * 60 / max([iv.lpm, *nbs])))
    return out


def level(ivs: list[Interval], max_s: float) -> float:
    """Flow (L/min) carrying most of the water: volume-weighted median over inner intervals."""
    wet = [i for i, iv in enumerate(ivs) if iv.litres > 0]
    inner = [i for i in wet if 0 < i < len(ivs) - 1 and ivs[i - 1].litres > 0 and ivs[i + 1].litres > 0
             and ivs[i].seconds <= max_s]
    if not inner:
        return max(ivs[i].lpm for i in wet)
    pts = sorted((ivs[i].lpm, ivs[i].litres) for i in inner)
    half, acc = sum(litres for _, litres in pts) / 2, 0.0
    for lpm, litres in pts:
        acc += litres
        if acc >= half:
            return lpm
    return pts[-1][0]


def main_run(ivs: list[Interval], lvl: float) -> tuple[int, int]:
    """First and last interval of the main run: the wet stretches (split by dry readings) from the
    first to the last one that reaches half the main flow level. A stretch is never cut, so a
    lower-flow part of the shower itself (hand shower) stays in, and side use needs a dry reading."""
    high = [i for i, iv in enumerate(ivs) if iv.litres > 0 and iv.lpm >= MAIN_LEVEL * lvl]
    a, b = high[0], high[-1]
    while a > 0 and ivs[a - 1].litres > 0:
        a -= 1
    while b + 1 < len(ivs) and ivs[b + 1].litres > 0:
        b += 1
    return a, b


def _span(ivs: list[Interval], taus: list[float]) -> tuple[float, float] | None:
    """Estimated first and last moment of running water."""
    wet = [i for i, iv in enumerate(ivs) if iv.litres > 0]
    if not wet:
        return None
    f, last = wet[0], wet[-1]
    if f == last:
        mid = (ivs[f].t0 + ivs[f].t1) / 2
        return mid - taus[f] / 2, mid + taus[f] / 2
    return ivs[f].t1 - taus[f], ivs[last].t0 + taus[last]


@dataclasses.dataclass
class Draw:
    start: float           # first water (epoch s)
    end: float             # last water
    volume_l: float
    flowing_s: float       # time the water actually ran
    level_lpm: float       # flow level carrying most of the water
    peak_lpm: float        # highest inner-interval flow of the main run
    main_start: float
    main_end: float
    main_volume_l: float
    main_flowing_s: float
    complete: bool         # False when a reading gap turns the timing into a guess
    readings: int

    def payload(self) -> dict:
        main_min = self.main_flowing_s / 60
        return {
            "start": _iso(self.start), "end": _iso(self.end), "volume_l": round(self.volume_l, 1),
            "duration_min": round((self.end - self.start) / 60, 2),
            "flowing_min": round(self.flowing_s / 60, 2),
            "main_start": _iso(self.main_start), "main_end": _iso(self.main_end),
            "main_volume_l": round(self.main_volume_l, 1),
            "main_duration_min": round((self.main_end - self.main_start) / 60, 2),
            "main_flowing_min": round(main_min, 2),
            "main_flow": round(self.main_volume_l / main_min, 2) if main_min > 0 else 0.0,
            "level_flow": round(self.level_lpm, 2), "peak_flow": round(self.peak_lpm, 2),
            "side_volume_l": round(self.volume_l - self.main_volume_l, 1),
            "side_flowing_min": round((self.flowing_s - self.main_flowing_s) / 60, 2),
            "complete": self.complete, "readings": self.readings,
        }


def analyse(points: list[tuple[float, float]], max_interval_s: float = 90) -> Draw | None:
    """points: (epoch s, total m3), from the last dry reading before the draw onwards."""
    ivs = [Interval(a[0], b[0], max(round((b[1] - a[1]) * 1000, 1), 0.0)) for a, b in zip(points, points[1:])]
    wet = [iv for iv in ivs if iv.litres > 0]
    if not wet:
        return None
    lvl = level(ivs, max_interval_s)
    a, b = main_run(ivs, lvl)
    regions = [ivs[:a], ivs[a:b + 1], ivs[b + 1:]]
    taus = [on_times(r) for r in regions]
    spans = [s for s in (_span(r, t) for r, t in zip(regions, taus)) if s]
    main = regions[1]
    inner = [iv.lpm for i, iv in enumerate(main) if 0 < i < len(main) - 1
             and main[i - 1].litres > 0 and iv.litres > 0 and main[i + 1].litres > 0]
    main_start, main_end = _span(main, taus[1])
    return Draw(
        start=min(s[0] for s in spans), end=max(s[1] for s in spans),
        volume_l=sum(iv.litres for iv in wet), flowing_s=sum(map(sum, taus)),
        level_lpm=lvl, peak_lpm=max(inner or [iv.lpm for iv in main if iv.litres > 0]),
        main_start=main_start, main_end=main_end,
        main_volume_l=sum(iv.litres for iv in main), main_flowing_s=sum(taus[1]),
        complete=all(iv.seconds <= max_interval_s for iv in wet), readings=len(points))


class DrawDetector:
    """Groups accepted readings into draws; a draw ends after `gap_s` without flow.

    add() returns the events to publish: {"event": "start", ...} on the first reading that shows
    flow and {"event": "end", ...Draw.payload()} once the gap has passed. An open draw is saved to
    `path` so it survives a restart.
    """

    def __init__(self, gap_s: float = 120, max_interval_s: float = 90, path: str | pathlib.Path | None = None):
        self.gap_s, self.max_interval_s = gap_s, max_interval_s
        self.path = pathlib.Path(path) if path else None
        self.points: list[list[float]] = []   # [ts, total m3]; [0] = last dry reading before the draw
        self.last_flow: float | None = None   # ts of the last reading that showed flow; None = no draw
        if self.path and self.path.exists():
            try:
                s = json.loads(self.path.read_text())
                self.points, self.last_flow = s["points"], s["last_flow"]
            except (ValueError, KeyError, TypeError):
                pass

    @property
    def open(self) -> bool:
        return self.last_flow is not None

    def seed(self, ts: float | None, total: float | None) -> None:
        """Last known reading (e.g. after a restart) as the dry reference, unless a draw is open."""
        if not self.open and ts and total is not None:
            self.points = [[ts, total]]

    def reset(self, ts: float, total: float) -> list[dict]:
        """Meter value was set: end an open draw and start counting from this reading."""
        events = [self._finish()] if self.open else []
        self.points = [[ts, total]]
        self._save()
        return [e for e in events if e]

    def add(self, ts: float, total: float) -> list[dict]:
        if not self.points:
            self.points = [[ts, total]]
            return []
        last_ts, last_total = self.points[-1]
        if ts <= last_ts:
            return []
        wet = total > last_total
        events = []
        if self.open and wet and ts - last_ts > self.gap_s:
            # Readings missing for longer than the gap: no way to tell if this is the same draw.
            events.append(self._finish())
        if not self.open:
            if wet:
                self.points = [self.points[-1], [ts, total]]
                self.last_flow = ts
                events.append({"event": "start", "after": _iso(self.points[0][0]), "seen": _iso(ts)})
            else:
                self.points = [[ts, total]]
        else:
            self.points.append([ts, total])
            if wet:
                self.last_flow = ts
            elif ts - self.last_flow >= self.gap_s:
                events.append(self._finish())
        if self.open or events:
            self._save()
        return [e for e in events if e]

    def _finish(self) -> dict | None:
        draw = analyse([tuple(p) for p in self.points], self.max_interval_s)
        self.points, self.last_flow = [self.points[-1]], None
        return {"event": "end", **draw.payload()} if draw else None

    def _save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"points": self.points, "last_flow": self.last_flow}))
