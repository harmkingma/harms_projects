"""Capture snapshots from the ESPHome meter camera, optionally with the flash LED on."""
import argparse
import datetime as dt
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "cv"))
from watermeter.camera import Camera  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="192.168.68.76")
parser.add_argument("--brightness", type=int, default=140, help="0 = no flash; ~55% gives least glare at 15 cm")
parser.add_argument("--settle", type=float, default=1.5, help="seconds for auto-exposure after flash on")
parser.add_argument("--count", type=int, default=1)
parser.add_argument("--interval", type=float, default=0, help="seconds between captures")
parser.add_argument("--out", default="dataset/raw")
parser.add_argument("--min-mean", type=float, default=40, help="reject frames darker than this (stale, pre-flash)")
parser.add_argument("--retries", type=int, default=4)
args = parser.parse_args()

camera = Camera(args.host, args.brightness, args.settle, args.min_mean, args.retries)
out_dir = pathlib.Path(args.out)
out_dir.mkdir(parents=True, exist_ok=True)

if sys.platform == "win32" and args.count > 1:
    import ctypes
    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED: block idle sleep while collecting (not lid-close sleep).
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

for i in range(args.count):
    t0 = time.monotonic()
    try:
        data = camera.capture()
    except Exception as exc:  # unattended runs: log and keep going (WiFi drop, reboot, dark frame)
        print(f"{dt.datetime.now():%H:%M:%S} capture failed: {exc}", flush=True)
        time.sleep(max(args.interval, 5))
        continue
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"{stamp}_b{args.brightness}.jpg"
    path.write_bytes(data)
    print(f"{path} {len(data)} bytes {time.monotonic() - t0:.2f}s", flush=True)
    if i + 1 < args.count:
        time.sleep(args.interval)
