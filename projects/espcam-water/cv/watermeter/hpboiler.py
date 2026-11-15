"""Smart heat-pump boiler on real solar export: yearly simulation from HA statistics.

A boiler heats only on surplus (export covering most of its power) up to the solar tank
temperature; the grid tops up to one peak shower session at 05:00 and otherwise keeps a small
comfort floor. Months without enough history are estimated from the measured month with the
most similar solar yield, scaled by a typical Dutch PV profile.
"""
from __future__ import annotations

import calendar
import dataclasses
import datetime as dt
import json
import urllib.request
from collections import defaultdict
from zoneinfo import ZoneInfo

COLD_WATER = [7, 6, 7, 9, 12, 15, 17, 18, 17, 14, 11, 8]           # NL mains water degC, Jan..Dec
PV_PROFILE = [22, 40, 75, 110, 130, 130, 130, 115, 85, 55, 25, 15]  # NL kWh/kWp per month
DEMAND_PROFILE = {6: 0.40, 7: 0.25, 12: 0.05, 18: 0.10, 19: 0.10, 21: 0.10}
MIN_DAYS = 7  # days of export history before a month counts as measured


@dataclasses.dataclass
class Params:
    heat_kwh_day: float = 6.0       # hot water heat per day at 10 degC mains
    peak_session_kwh: float = 7.0   # heat of the largest session the 05:00 top-up must cover
    tank_l: float = 200
    t_solar: float = 60
    t_shower: float = 40
    cop: float = 2.8
    heat_kw: float = 1.5
    standby_kwh_day: float = 1.0
    min_surplus_share: float = 0.7  # boiler starts when export covers this share of its power
    floor_share: float = 0.15       # comfort floor (share of capacity) the grid keeps all day
    topup_hour: int = 5


@dataclasses.dataclass
class MonthResult:
    hours: int = 0
    heat: float = 0.0
    solar_el: float = 0.0
    grid_el: float = 0.0


def simulate(export_by_hour: dict[dt.datetime, float], p: Params) -> dict[tuple[int, int], MonthResult]:
    """export_by_hour: local hour start -> exported kWh in that hour."""
    el_kw = p.heat_kw / p.cop
    months: dict[tuple[int, int], MonthResult] = defaultdict(MonthResult)
    stored = None
    for hour in sorted(export_by_hour):
        cold = COLD_WATER[hour.month - 1]
        capacity = p.tank_l * 4.186 * (p.t_solar - cold) / 3600
        session = min(p.peak_session_kwh * (p.t_shower - cold) / (p.t_shower - 10), capacity)
        reserve = session if hour.hour == p.topup_hour else p.floor_share * capacity
        if stored is None:
            stored = session
        m = months[(hour.year, hour.month)]
        export = export_by_hour[hour]
        solar = grid = 0.0
        if export >= p.min_surplus_share * el_kw and stored < capacity:
            run = min(1.0, (capacity - stored) / (el_kw * p.cop))
            solar = min(export, el_kw) * run
            grid = el_kw * run - solar
            stored += el_kw * run * p.cop
        demand = p.heat_kwh_day * (p.t_shower - cold) / (p.t_shower - 10) * DEMAND_PROFILE.get(hour.hour, 0.0)
        stored -= demand + p.standby_kwh_day / 24
        if stored < reserve:
            grid += (reserve - stored) / p.cop
            stored = reserve
        m.hours += 1
        m.heat += demand
        m.solar_el += solar
        m.grid_el += grid
    return months


def build_year(export_by_hour: dict[dt.datetime, float], today: dt.date):
    """Hourly export for the last 12 calendar months, measured where possible, else estimated.

    Returns (hours dict, list of month info dicts) or ({}, []) without a measured month.
    """
    days: dict[tuple[int, int], dict[dt.date, list[float]]] = defaultdict(dict)
    for t, v in export_by_hour.items():
        days[(t.year, t.month)].setdefault(t.date(), [0.0] * 24)[t.hour] = v
    measured = {k: d for k, d in days.items() if len(d) >= MIN_DAYS}
    if not measured:
        return {}, []
    keys, y, m = [], today.year, today.month
    for _ in range(12):
        keys.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    hours: dict[dt.datetime, float] = {}
    info = []
    for key in reversed(keys):
        month_days = calendar.monthrange(*key)[1]
        if key in measured:
            for d, vals in measured[key].items():
                hours.update({dt.datetime(d.year, d.month, d.day, h): v for h, v in enumerate(vals)})
            info.append({"month": f"{key[0]}-{key[1]:02d}", "source": "measured", "days": len(measured[key]),
                         "scale": month_days / len(measured[key])})
            continue
        src = min(measured, key=lambda k: (abs(PV_PROFILE[k[1] - 1] - PV_PROFILE[key[1] - 1]), -len(measured[k])))
        factor = PV_PROFILE[key[1] - 1] / PV_PROFILE[src[1] - 1]
        src_days = [measured[src][d] for d in sorted(measured[src])]
        for i in range(month_days):
            vals = src_days[i % len(src_days)]
            hours.update({dt.datetime(key[0], key[1], i + 1, h): v * factor for h, v in enumerate(vals)})
        info.append({"month": f"{key[0]}-{key[1]:02d}", "source": f"estimated from {src[0]}-{src[1]:02d}",
                     "days": month_days, "scale": 1.0})
    return hours, info


def year_summary(export_by_hour: dict[dt.datetime, float], p: Params, today: dt.date) -> dict | None:
    hours, info = build_year(export_by_hour, today)
    if not hours:
        return None
    results = simulate(hours, p)
    months, solar, grid, heat = [], 0.0, 0.0, 0.0
    for mi in info:
        y, m = map(int, mi["month"].split("-"))
        r = results[(y, m)]
        s, g, h = r.solar_el * mi["scale"], r.grid_el * mi["scale"], r.heat * mi["scale"]
        solar, grid, heat = solar + s, grid + g, heat + h
        months.append({"month": mi["month"], "source": mi["source"], "days": mi["days"],
                       "solar_share": round(100 * s / (s + g)) if s + g else 0,
                       "solar_kwh": round(s, 1), "grid_kwh": round(g, 1)})
    return {"solar_share": round(100 * solar / (solar + grid), 1) if solar + grid else 0.0,
            "solar_kwh": round(solar), "grid_kwh": round(grid), "heat_kwh": round(heat),
            "measured_months": sum(m["source"] == "measured" for m in months), "months": months}


def num(states: dict[str, str], entity_id: str, default: float) -> float:
    try:
        return float(states[entity_id])
    except (KeyError, TypeError, ValueError):
        return default


def params_from_states(s: dict[str, str]) -> tuple[Params, list[str]]:
    """Boiler parameters from the water_usage package helpers and measured hot water use."""
    notes = []
    t_shower = num(s, "input_number.wm_shower_temp", 40)
    days = num(s, "sensor.usage_tracking_days", 0)
    gas = num(s, "sensor.gas_hot_water_total", 0)
    if days >= 3 and gas > 0:
        heat_day = gas / days * num(s, "input_number.wm_gas_kwh_per_m3", 9.77) \
            * num(s, "input_number.wm_combi_efficiency", 85) / 100
    else:
        heat_day = 6.0
        notes.append("hot water demand: default 6 kWh/day (less than 3 days measured)")
    peak_l = num(s, "input_number.wm_hot_peak_session_v40", 0)
    if peak_l > 0:
        peak = peak_l * (1 + num(s, "input_number.wm_boiler_margin", 20) / 100) * 4.186 * (t_shower - 10) / 3600
    else:
        peak = 7.0
        notes.append("peak session: default 7 kWh (none measured yet)")
    return Params(heat_kwh_day=heat_day, peak_session_kwh=peak,
                  tank_l=num(s, "input_number.wm_hp_boiler_tank_l", 200),
                  t_solar=num(s, "input_number.wm_solar_tank_temp", 60), t_shower=t_shower,
                  cop=max(num(s, "input_number.wm_hp_boiler_cop", 2.8), 0.5),
                  heat_kw=num(s, "input_number.wm_hp_boiler_heat_kw", 1.5),
                  standby_kwh_day=num(s, "input_number.wm_hp_boiler_standby_kwh", 1.0)), notes


class HomeAssistant:
    """Minimal REST + websocket client (Supervisor proxy inside an add-on, or direct with a token)."""

    def __init__(self, rest_url: str, ws_url: str, token: str):
        self.rest_url, self.ws_url, self.token = rest_url.rstrip("/"), ws_url, token

    def _get(self, path: str):
        req = urllib.request.Request(f"{self.rest_url}{path}", headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)

    def states(self) -> dict[str, str]:
        return {s["entity_id"]: s["state"] for s in self._get("/states")}

    def time_zone(self) -> ZoneInfo:
        return ZoneInfo(self._get("/config").get("time_zone", "UTC"))

    def _ws(self, msg: dict):
        from websockets.sync.client import connect

        with connect(self.ws_url, max_size=2**26, open_timeout=30) as ws:
            ws.recv()
            ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            if json.loads(ws.recv()).get("type") != "auth_ok":
                raise RuntimeError("Home Assistant websocket authentication failed")
            ws.send(json.dumps({"id": 1, **msg}))
            reply = json.loads(ws.recv())
        if not reply.get("success", False):
            raise RuntimeError(f"websocket {msg['type']} failed: {reply.get('error')}")
        return reply["result"]

    def export_statistics(self) -> list[str]:
        ids = self._ws({"type": "recorder/list_statistic_ids", "statistic_type": "sum"})
        return [s["statistic_id"] for s in ids if "export" in s["statistic_id"]
                and (s.get("statistics_unit_of_measurement") or "").lower() == "kwh"]

    def hourly_export(self, stat_id: str, days: int = 365) -> dict[dt.datetime, float]:
        tz = self.time_zone()
        end = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
        rows = self._ws({"type": "recorder/statistics_during_period", "statistic_ids": [stat_id],
                         "period": "hour", "types": ["change"],
                         "start_time": (end - dt.timedelta(days=days)).isoformat(),
                         "end_time": end.isoformat()}).get(stat_id, [])
        out = {}
        for r in rows:
            s = r["start"]
            ts = s / 1000 if isinstance(s, (int, float)) else dt.datetime.fromisoformat(s).timestamp()
            out[dt.datetime.fromtimestamp(ts, tz).replace(tzinfo=None)] = max(float(r.get("change") or 0.0), 0.0)
        return out
