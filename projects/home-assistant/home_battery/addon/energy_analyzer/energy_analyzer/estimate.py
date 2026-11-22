"""Estimated hourly use for hours without meter data, from the real weather of those hours.

Fitted on the measured hours (P1 import/export + solar production statistics):
    solar        kWh = k x tilted irradiance (kWh/m2), capped at the peak power
    consumption  per day = base + heat x HDD + cool x CDD, spread over the day with hourly shapes
                 (base from mild days, heating and cooling from the residual of cold and hot days)
                 HDD = max(0, 16 - daily mean), CDD = max(0, daily maximum - 24)
    gas          per day = base + heat x HDD, spread evenly
Import/export of an estimated hour = consumption - solar netted per hour. Weather: Open-Meteo
historical archive (ERA5, about 5 days behind), cached in /data.
"""
from __future__ import annotations

import bisect
import dataclasses
import datetime as dt
import json
import logging
import pathlib
import urllib.parse
import urllib.request
from collections import defaultdict

from .model import Hour

log = logging.getLogger(__name__)
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
ARCHIVE_LAG_DAYS = 6
HEAT_BASE = 16.0          # degC daily mean
COOL_BASE = 24.0          # degC daily maximum
PERFORMANCE_RATIO = 0.85  # kWh per kWh/m2 per kWp, used when there is too little solar data to fit
MIN_FIT_DAYS = 14


@dataclasses.dataclass
class Site:
    latitude: float
    longitude: float
    tilt: float = 35.0
    azimuth: float = -22.0  # 0 = south, negative = east
    kwp: float = 4.1

    def key(self) -> str:
        return f"{self.latitude:.2f},{self.longitude:.2f},{self.tilt:g},{self.azimuth:g}"


def fetch_weather(site: Site, first: dt.date, last: dt.date) -> dict[int, tuple[float, float]]:
    """Hour start epoch -> (temperature degC, mean tilted irradiance W/m2 over that hour)."""
    query = urllib.parse.urlencode({
        "latitude": f"{site.latitude:.2f}", "longitude": f"{site.longitude:.2f}",
        "start_date": first.isoformat(), "end_date": last.isoformat(),
        "hourly": "temperature_2m,global_tilted_irradiance", "tilt": site.tilt, "azimuth": site.azimuth,
        "timeformat": "unixtime", "timezone": "GMT"})
    with urllib.request.urlopen(f"{ARCHIVE_URL}?{query}", timeout=120) as resp:
        hourly = json.load(resp)["hourly"]
    temp = dict(zip(hourly["time"], hourly["temperature_2m"]))
    # Radiation is the mean over the preceding hour: the value at t + 1 h belongs to the hour starting at t.
    gti = dict(zip(hourly["time"], hourly["global_tilted_irradiance"]))
    return {int(t): (float(temp[t]), float(gti[t + 3600])) for t in temp
            if temp[t] is not None and gti.get(t + 3600) is not None}


class WeatherCache:
    def __init__(self, path: pathlib.Path, site: Site):
        self.path, self.site = path, site
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        same = data.get("key") == site.key()
        self.hours = {int(k): tuple(v) for k, v in data.get("hours", {}).items()} if same else {}

    def fill(self, first: dt.date, last: dt.date, tz, fetch=fetch_weather) -> None:
        last = min(last, dt.date.today() - dt.timedelta(days=ARCHIVE_LAG_DAYS))
        per_day: dict[dt.date, int] = defaultdict(int)
        for t in self.hours:
            per_day[dt.datetime.fromtimestamp(t, tz).date()] += 1
        missing = [first + dt.timedelta(days=i) for i in range((last - first).days + 1)
                   if per_day[first + dt.timedelta(days=i)] < 23]
        if not missing:
            return
        self.hours.update(fetch(self.site, missing[0], missing[-1]))
        log.info("weather %s..%s: %d hours cached", missing[0], missing[-1], len(self.hours))
        self.path.write_text(json.dumps({"key": self.site.key(), "hours": self.hours}))


def degree_days(weather: dict[int, tuple[float, float]], tz) -> dict[dt.date, tuple[float, float]]:
    temps: dict[dt.date, list[float]] = defaultdict(list)
    for t, (temp, _) in weather.items():
        temps[dt.datetime.fromtimestamp(t, tz).date()].append(temp)
    return {d: (max(0.0, HEAT_BASE - sum(v) / len(v)), max(0.0, max(v) - COOL_BASE))
            for d, v in temps.items() if len(v) >= 20}


def _solve(rows: list[list[float]], y: list[float]) -> list[float]:
    """Least squares via the normal equations (a handful of columns)."""
    n = len(rows[0])
    a = [[sum(r[i] * r[j] for r in rows) for j in range(n)] + [sum(r[i] * v for r, v in zip(rows, y))]
         for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        if abs(a[col][col]) < 1e-12:
            return [0.0] * n
        for r in range(n):
            if r != col:
                f = a[r][col] / a[col][col]
                a[r] = [x - f * p for x, p in zip(a[r], a[col])]
    return [a[i][n] / a[i][i] for i in range(n)]


def fit_nonnegative(rows: list[list[float]], y: list[float], nonneg: tuple[int, ...]) -> list[float]:
    """Least squares; columns in nonneg that come out negative are dropped (set to 0) and the rest refitted."""
    active = list(range(len(rows[0])))
    while True:
        coef = _solve([[r[i] for i in active] for r in rows], y)
        full = [0.0] * len(rows[0])
        for i, c in zip(active, coef):
            full[i] = c
        worst = min((i for i in active if i in nonneg and full[i] < 0), key=lambda i: full[i], default=None)
        if worst is None:
            return full
        active.remove(worst)


def _normalise(values: list[float], fallback: list[float]) -> list[float]:
    total = sum(max(v, 0.0) for v in values)
    return [max(v, 0.0) / total for v in values] if total > 1e-9 else fallback


FLAT = [1 / 24] * 24
AFTERNOON = [0.0] * 12 + [0.1] * 10 + [0.0] * 2


@dataclasses.dataclass
class UseModel:
    solar_k: float
    base: float
    heat: float
    cool: float
    gas_base: float
    gas_heat: float
    shape_base: list[float]
    shape_heat: list[float]
    shape_cool: list[float]
    fit_days: int
    use_error_pct: float
    solar_error_pct: float | None

    def summary(self) -> dict:
        return {"solar_kwh_per_kwh_m2": round(self.solar_k, 2), "base_kwh_day": round(self.base, 1),
                "heating_kwh_per_degree_day": round(self.heat, 2), "cooling_kwh_per_degree_day": round(self.cool, 2),
                "gas_base_m3_day": round(self.gas_base, 2), "gas_m3_per_degree_day": round(self.gas_heat, 3),
                "fit_days": self.fit_days, "use_error_pct": round(self.use_error_pct, 1),
                "solar_error_pct": None if self.solar_error_pct is None else round(self.solar_error_pct, 1)}


def fit(hours: list[Hour], solar: dict[int, float], weather: dict[int, tuple[float, float]], tz,
        site: Site) -> UseModel | None:
    """Fit on measured hours that have a solar statistic; None with fewer than MIN_FIT_DAYS full days."""
    num = den = 0.0
    day_solar: dict[dt.date, list[float]] = defaultdict(lambda: [0.0, 0.0])
    days: dict[dt.date, dict] = defaultdict(lambda: {"n": 0, "use": [0.0] * 24, "gas": 0.0})
    for h in hours:
        ts = int(h.t.timestamp())
        if h.estimated or ts not in solar:
            continue
        d = h.t.date()
        if ts in weather:
            g = weather[ts][1] / 1000
            num, den = num + solar[ts] * g, den + g * g
            day_solar[d][0] += solar[ts]
            day_solar[d][1] += g
        rec = days[d]
        rec["n"] += 1
        rec["use"][h.t.hour] += max(h.imp + solar[ts] - h.exp, 0.0)
        rec["gas"] += h.gas
    k = num / den if den > 0.5 else site.kwp * PERFORMANCE_RATIO
    dd = degree_days(weather, tz)
    full = sorted(d for d, r in days.items() if r["n"] >= 23 and d in dd)
    if len(full) < MIN_FIT_DAYS:
        return None
    use = [sum(days[d]["use"]) for d in full]
    base, heat, cool = fit_nonnegative([[1.0, *dd[d]] for d in full], use, (1, 2))
    gas_base, gas_heat = fit_nonnegative([[1.0, dd[d][0]] for d in full], [days[d]["gas"] for d in full], (1,))
    mild = [d for d in full if dd[d][0] < 1 and dd[d][1] == 0] or full
    shape_base = _normalise([sum(days[d]["use"][i] for d in mild) for i in range(24)], FLAT)
    cold = [d for d in full if dd[d][0] >= 3]
    shape_heat = _normalise([sum(days[d]["use"][i] - base * shape_base[i] for d in cold) for i in range(24)], FLAT)
    hot = [d for d in full if dd[d][1] >= 2]
    shape_cool = _normalise([sum(days[d]["use"][i] - base * shape_base[i] - heat * dd[d][0] * shape_heat[i]
                                 for d in hot) for i in range(24)], AFTERNOON)
    predicted = [base + heat * dd[d][0] + cool * dd[d][1] for d in full]
    use_error = 100 * sum(abs(p - u) for p, u in zip(predicted, use)) / max(sum(use), 1e-9)
    sun = [v for d, v in day_solar.items() if d in days and v[0] > 0]
    solar_error = 100 * sum(abs(k * g - s) for s, g in sun) / sum(s for s, _ in sun) if sun else None
    return UseModel(k, base, heat, cool, max(gas_base, 0.0), gas_heat, shape_base, shape_heat, shape_cool,
                    len(full), use_error, solar_error)


def synthesize(model: UseModel, missing: list[int], weather: dict[int, tuple[float, float]],
               electricity: dict[int, float], gas_prices: dict[int, float], tz, site: Site) -> list[Hour]:
    """Estimated hours for the given hour starts (skipped without weather or electricity price)."""
    dd = degree_days(weather, tz)
    gas_times = sorted(gas_prices)
    out = []
    for ts in missing:
        t = dt.datetime.fromtimestamp(ts, tz)
        if ts not in weather or ts not in electricity or t.date() not in dd:
            continue
        hdd, cdd = dd[t.date()]
        i = t.hour
        use = (model.base * model.shape_base[i] + model.heat * hdd * model.shape_heat[i]
               + model.cool * cdd * model.shape_cool[i])
        sun = min(model.solar_k * weather[ts][1] / 1000, site.kwp)
        k = bisect.bisect_right(gas_times, ts) - 1
        out.append(Hour(t=t, imp=max(use - sun, 0.0), exp=max(sun - use, 0.0), market=electricity[ts],
                        gas=max(model.gas_base + model.gas_heat * hdd, 0.0) / 24,
                        gas_market=gas_prices[gas_times[k]] if k >= 0 else None, estimated=True))
    return out
