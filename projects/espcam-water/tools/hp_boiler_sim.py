"""Debug run of the boiler year simulation from the laptop (the add-on runs it nightly on the Pi).

  $env:HA_TOKEN = '<long-lived access token>'
  python tools/hp_boiler_sim.py [--export-stat sensor.p1_meter_energy_export]
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "cv"))
from watermeter.hpboiler import HomeAssistant, params_from_states, year_summary  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://homeassistant.local:8123")
ap.add_argument("--export-stat", help="grid export energy statistic (default: auto-detect)")
args = ap.parse_args()
token = os.environ.get("HA_TOKEN") or sys.exit("set HA_TOKEN first")
ha = HomeAssistant(f"{args.url}/api", args.url.replace("http", "ws", 1) + "/api/websocket", token)
stat = args.export_stat or (ha.export_statistics() or [None])[0] or sys.exit("no export statistic found")
params, notes = params_from_states(ha.states())
summary = year_summary(ha.hourly_export(stat), params, dt.date.today())
print(f"export statistic: {stat}\n{params}\n" + "\n".join(notes))
print(json.dumps(summary, indent=1) if summary else "not enough export history yet")
