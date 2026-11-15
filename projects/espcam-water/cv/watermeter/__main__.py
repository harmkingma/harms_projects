"""CLI: python -m watermeter {read,export-digits,draws} ..."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import pathlib
import re
import time

import cv2

from .digits import crop_digits
from .draws import DrawDetector
from .learning import DigitLearner
from .pipeline import MeterReader
from .tracker import MeterTracker

STAMP = re.compile(r"(\d{8}_\d{6})")


def image_time(path: pathlib.Path) -> float | None:
    m = STAMP.search(path.name)
    return dt.datetime.strptime(m.group(1), "%Y%m%d_%H%M%S").timestamp() if m else None


def image_paths(args: list[str]) -> list[pathlib.Path]:
    """Files and/or directories (all *.jpg inside), sorted by name."""
    paths = []
    for a in map(pathlib.Path, args):
        paths.extend(a.glob("*.jpg") if a.is_dir() else [a])
    return sorted(paths)


def cmd_read(args: argparse.Namespace) -> None:
    learner = DigitLearner(args.learn) if args.learn else None
    reader = MeterReader(args.config, *([learner.digits_dir] if learner else []))
    tracker = MeterTracker(reader, args.state, learner) if args.state else None
    if tracker:
        tracker.apply_start_value(args.initial)
    out = pathlib.Path(args.annotate) if args.annotate else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    previous, prev_t = args.initial, None
    for path in image_paths(args.images):
        img = cv2.imread(str(path))
        t0 = time.perf_counter()
        t = image_time(path)
        if tracker:
            res = tracker.process(img, t)
        else:
            res = reader.read(img, previous, (t - prev_t) if t and prev_t else None)
        ms = (time.perf_counter() - t0) * 1000
        rd = res.reading
        print(json.dumps({
            "image": path.name, "total": rd.total, "status": rd.status, "detail": rd.detail,
            "digits": rd.digits, "dials": [round(v, 2) for v in rd.dials],
            "raw_dials": [round(d.value, 2) for d in res.dials],
            "dial_conf": [round(d.confidence, 2) for d in res.dials],
            "inliers": res.inliers, "ms": round(ms),
        }))
        if rd.total is not None and args.track:
            previous, prev_t = rd.total, t
        if out:
            cv2.imwrite(str(out / f"{path.stem}_read.jpg"), reader.annotate(res))


def cmd_export_digits(args: argparse.Namespace) -> None:
    reader = MeterReader(args.config)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for path in image_paths(args.images):
        al = reader.aligner.align(cv2.imread(str(path)))
        if not al.ok:
            print(f"{path.name}: alignment failed ({al.inliers} inliers)")
            continue
        for i, crop in enumerate(crop_digits(al.canonical, reader.cfg.digit_boxes)):
            cv2.imwrite(str(out / f"{path.stem}_d{i}.png"), crop)
    print(f"crops written to {out}; move them into {pathlib.Path(args.config).parent / 'digits'}/<0-9>/")


def load_readings(path: pathlib.Path, interval_s: float) -> list[tuple[float, float]]:
    """(epoch s, total m3) from `read` JSON lines, or an HA history CSV of sensor.water_meter_total."""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() != ".csv":
        pts = []
        for line in text.splitlines():
            if line.startswith("{"):
                r = json.loads(line.replace("NaN", "null"))
                t = image_time(pathlib.Path(r.get("image", "")))
                if r.get("total") is not None and t:
                    pts.append((t, r["total"]))
        return pts
    changes = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            changes.append((dt.datetime.fromisoformat(row["last_changed"]).timestamp(), float(row["state"])))
        except (KeyError, ValueError):  # unavailable / unknown
            continue
    changes.sort()
    # HA stores changes only: put back the unchanged readings next to each change.
    pts = changes[:1]
    for (ta, va), (tb, vb) in zip(changes, changes[1:]):
        if tb - ta > 2.5 * interval_s:
            pts.append((ta + interval_s, va))
        if tb - ta > 1.5 * interval_s:
            pts.append((tb - interval_s, va))
        pts.append((tb, vb))
    return pts


def cmd_draws(args: argparse.Namespace) -> None:
    pts = load_readings(pathlib.Path(args.readings), args.interval)
    det = DrawDetector(args.gap, max(3 * args.interval, 90))

    def local(iso_ts: str) -> str:
        return dt.datetime.fromisoformat(iso_ts).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    # One extra dry reading after the data closes the last draw.
    for t, total in pts + ([(pts[-1][0] + args.gap, pts[-1][1])] if pts else []):
        for e in det.add(t, total):
            if e["event"] != "end":
                continue
            if args.json:
                print(json.dumps(e))
                continue
            side = f"  side {e['side_volume_l']:.1f} L" if e["side_volume_l"] else ""
            print(f"{local(e['main_start'])}  {e['main_volume_l']:6.1f} L  {e['main_duration_min']:5.1f} min, "
                  f"flowing {e['main_flowing_min']:5.2f} min = {e['main_flow']:5.2f} L/min "
                  f"(peak {e['peak_flow']:.1f}){side}{'' if e['complete'] else '  [reading gap]'}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="watermeter")
    sub = ap.add_subparsers(required=True)
    r = sub.add_parser("read", help="read meter images")
    r.add_argument("images", nargs="+", help="image files and/or directories")
    r.add_argument("--config", default="cv/meter.yaml")
    r.add_argument("--annotate", help="write annotated images to this dir")
    r.add_argument("--initial", type=float, help="start value: meter reading (m3) before the first image")
    r.add_argument("--track", action="store_true", help="stateless mode: use each reading as the previous value")
    r.add_argument("--state", help="state file; enables persistent tracking (start value applied once)")
    r.add_argument("--learn", help="store dir for self-learned digits (digits/ and review/)")
    r.set_defaults(func=cmd_read)
    e = sub.add_parser("export-digits", help="export digit crops for labelling")
    e.add_argument("images", nargs="+")
    e.add_argument("--config", default="cv/meter.yaml")
    e.add_argument("--out", default="dataset/digit_crops")
    e.set_defaults(func=cmd_export_digits)
    d = sub.add_parser("draws", help="water draws (start/stop, flowing time, flow) from readings")
    d.add_argument("readings", help="JSON lines from `read`, or an HA history CSV of sensor.water_meter_total")
    d.add_argument("--interval", type=float, default=30, help="reading interval of the data (s)")
    d.add_argument("--gap", type=float, default=120, help="a draw ends after this long without flow (s)")
    d.add_argument("--json", action="store_true", help="print the full draw messages")
    d.set_defaults(func=cmd_draws)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
