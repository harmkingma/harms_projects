"""Stage the HA add-on: copy the watermeter package and calibration into addon/water_meter_reader/app/
and zip the add-on folder to dist/water_meter_reader.zip (unzip into the HA /addons share)."""
import pathlib
import shutil
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CV = ROOT / "cv"
ADDON = ROOT / "addon" / "water_meter_reader"
APP = ADDON / "app"

shutil.rmtree(APP, ignore_errors=True)
shutil.copytree(CV / "watermeter", APP / "watermeter", ignore=shutil.ignore_patterns("__pycache__"))
(APP / "cv").mkdir(parents=True)
shutil.copy2(CV / "meter.yaml", APP / "cv" / "meter.yaml")
shutil.copytree(CV / "digits", APP / "cv" / "digits")
ref = __import__("yaml").safe_load((CV / "meter.yaml").read_text())["reference"]
(APP / "cv" / ref).parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(CV / ref, APP / "cv" / ref)

dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
out = dist / "water_meter_reader.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(ADDON.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            zf.write(f, f.relative_to(ADDON.parent).as_posix())
print(f"staged {APP}\nzip    {out} ({out.stat().st_size // 1024} KB)")
