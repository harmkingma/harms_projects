"""Home Assistant access for the Energy Analyzer: hourly statistics, EnergyZero prices, helper settings."""
from __future__ import annotations

import bisect
import datetime as dt
import json
import logging
import pathlib
import urllib.request
from zoneinfo import ZoneInfo

from .model import GRID_SUMMER, GRID_WINTER, Battery, Contract, GridTariff, Hour, parse_profile

log = logging.getLogger(__name__)
PRICE_SENSOR = "sensor.hb_electricity_prices"  # packages/home_battery.yaml; has the config_entry attribute
CHUNK_DAYS = 31


class HomeAssistant:
    """Minimal REST + websocket client (Supervisor proxy inside an add-on, or direct with a token)."""

    def __init__(self, rest_url: str, ws_url: str, token: str):
        self.rest_url, self.ws_url, self.token = rest_url.rstrip("/"), ws_url, token

    def _request(self, path: str, body: dict | None = None, timeout: int = 60):
        req = urllib.request.Request(f"{self.rest_url}{path}", headers={"Authorization": f"Bearer {self.token}",
                                                                         "Content-Type": "application/json"},
                                     data=None if body is None else json.dumps(body).encode())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)

    def states(self) -> dict[str, dict]:
        return {s["entity_id"]: s for s in self._request("/states")}

    def config(self) -> dict:
        return self._request("/config")

    def time_zone(self) -> ZoneInfo:
        return ZoneInfo(self.config().get("time_zone", "UTC"))

    def service(self, domain: str, service: str, data: dict):
        return self._request(f"/services/{domain}/{service}?return_response", data, timeout=120)["service_response"]

    def _ws(self, msg: dict):
        from websockets.sync.client import connect

        with connect(self.ws_url, max_size=2**27, open_timeout=30) as ws:
            ws.recv()
            ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            if json.loads(ws.recv()).get("type") != "auth_ok":
                raise RuntimeError("Home Assistant websocket authentication failed")
            ws.send(json.dumps({"id": 1, **msg}))
            reply = json.loads(ws.recv())
        if not reply.get("success", False):
            raise RuntimeError(f"websocket {msg['type']} failed: {reply.get('error')}")
        return reply["result"]

    def hourly_changes(self, stat_ids: list[str], start: dt.datetime, end: dt.datetime) -> dict[str, dict[int, float]]:
        """statistic id -> {hour start epoch: change}; negative changes (meter resets) count as 0."""
        rows = self._ws({"type": "recorder/statistics_during_period", "statistic_ids": stat_ids, "period": "hour",
                         "types": ["change"], "start_time": start.isoformat(), "end_time": end.isoformat()})
        return {sid: {int(epoch(r["start"])): max(float(r.get("change") or 0.0), 0.0) for r in rows.get(sid, [])}
                for sid in stat_ids}

    def import_statistics(self, statistic_id: str, name: str, unit: str, rows: list[tuple[int, float]]) -> None:
        """Write hourly means as external statistics (source energy_analyzer); same hours are overwritten."""
        stats = [{"start": dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(), "mean": v, "min": v, "max": v}
                 for ts, v in rows]
        self._ws({"type": "recorder/import_statistics",
                  "metadata": {"source": "energy_analyzer", "statistic_id": f"energy_analyzer:{statistic_id}",
                               "name": name, "unit_of_measurement": unit, "unit_class": None,
                               "has_sum": False, "mean_type": 1},
                  "stats": stats})


def epoch(value) -> float:
    if isinstance(value, (int, float)):
        return value / 1000 if value > 1e11 else float(value)
    return dt.datetime.fromisoformat(str(value).replace(" ", "T")).timestamp()


class PriceCache:
    """Past EnergyZero prices by hour start epoch, kept in /data so each night only fetches new days."""

    def __init__(self, path: pathlib.Path):
        self.path = path
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        self.electricity = {int(k): v for k, v in data.get("electricity", {}).items()}
        self.gas = {int(k): v for k, v in data.get("gas", {}).items()}
        self.done = set(data.get("done", []))
        self.unavailable = set(data.get("unavailable", []))

    def save(self) -> None:
        self.path.write_text(json.dumps({"electricity": self.electricity, "gas": self.gas,
                                         "done": sorted(self.done), "unavailable": sorted(self.unavailable)}))

    def fill(self, ha: HomeAssistant, entry: str, days: list[dt.date], tz: ZoneInfo) -> None:
        """Fetch the days not cached yet; the service fetches start..end (dates) inclusive, hourly by default.

        A day without data fails the whole call, so a failing chunk is retried day by day and days that
        still fail are remembered and skipped from then on.
        """
        missing = [d for d in days if d.isoformat() not in self.done and d.isoformat() not in self.unavailable]
        for i in range(0, len(missing), CHUNK_DAYS):
            chunk = missing[i:i + CHUNK_DAYS]
            try:
                self._fetch(ha, entry, chunk[0], chunk[-1])
            except Exception as err:  # noqa: BLE001 - narrowed down per day below
                log.warning("prices %s..%s failed (%s), fetching day by day", chunk[0], chunk[-1], err)
                for d in chunk:
                    try:
                        self._fetch(ha, entry, d, d)
                    except Exception:  # noqa: BLE001
                        self.unavailable.add(d.isoformat())
            for d in chunk:
                first = dt.datetime.combine(d, dt.time(), tz).timestamp()
                if sum(first <= t < first + 90000 for t in self.electricity) >= 23:
                    self.done.add(d.isoformat())
        self.save()

    def _fetch(self, ha: HomeAssistant, entry: str, first: dt.date, last: dt.date) -> None:
        span = {"config_entry": entry, "incl_vat": True, "start": first.isoformat(), "end": last.isoformat()}
        elec = ha.service("energyzero", "get_energy_prices", span)
        gas = ha.service("energyzero", "get_gas_prices", span)
        for p in elec.get("prices", []):
            self.electricity[int(epoch(p["timestamp"]))] = float(p["price"])
        for p in gas.get("prices", []):
            self.gas[int(epoch(p["timestamp"]))] = float(p["price"])
        log.info("prices %s..%s: %d electricity, %d gas entries", first, last,
                 len(elec.get("prices", [])), len(gas.get("prices", [])))


def build_hours(changes: dict[str, dict[int, float]], ids: dict[str, str], prices: PriceCache,
                tz: ZoneInfo) -> list[Hour]:
    """Hours with an import statistic and an electricity price; gas price = latest one published."""
    gas_times = sorted(prices.gas)
    hours = []
    for ts in sorted(changes[ids["import"]]):
        market = prices.electricity.get(ts)
        if market is None:
            continue
        k = bisect.bisect_right(gas_times, ts) - 1
        hours.append(Hour(t=dt.datetime.fromtimestamp(ts, tz), imp=changes[ids["import"]][ts],
                          exp=changes[ids["export"]].get(ts, 0.0), market=market,
                          gas=changes.get(ids["gas"], {}).get(ts, 0.0),
                          gas_market=prices.gas[gas_times[k]] if k >= 0 else None))
    return hours


def _num(states: dict[str, dict], entity_id: str, default: float) -> float:
    try:
        return float(states[entity_id]["state"])
    except (KeyError, TypeError, ValueError):
        return default


def settings_from_states(s: dict[str, dict]) -> tuple[Battery, Contract, GridTariff, float]:
    """Battery, contract and grid tariff from the home_battery package helpers (defaults if missing)."""
    b, c, g = Battery(), Contract(), GridTariff()
    n = lambda key, default: _num(s, f"input_number.hb_{key}", default)  # noqa: E731
    battery = Battery(capacity_kwh=max(n("battery_capacity", b.capacity_kwh), 0.1),
                      power_kw=max(n("battery_power", b.power_kw), 0.05),
                      round_trip=n("battery_efficiency", b.round_trip * 100) / 100,
                      standby_w=n("battery_standby", b.standby_w), min_spread=n("battery_min_spread", b.min_spread),
                      investment=n("battery_investment", b.investment))
    contract = Contract(
        fixed_import=n("fixed_price", c.fixed_import), fixed_feed_in=n("fixed_feed_in", c.fixed_feed_in),
        fixed_feed_in_cost=n("fixed_feed_in_cost", c.fixed_feed_in_cost),
        fixed_monthly=n("fixed_monthly", c.fixed_monthly), dyn_markup=n("dynamic_markup", c.dyn_markup),
        energy_tax=n("energy_tax", c.energy_tax), dyn_feed_in_fee=n("dynamic_feed_in_fee", c.dyn_feed_in_fee),
        dyn_export_vat=s.get("input_boolean.hb_dynamic_export_vat", {}).get("state", "off") == "on",
        dyn_monthly=n("dynamic_monthly", c.dyn_monthly), gas_fixed=n("gas_fixed_price", c.gas_fixed),
        gas_markup=n("gas_dynamic_markup", c.gas_markup), gas_tax=n("gas_tax", c.gas_tax),
        gas_fixed_monthly=n("gas_fixed_monthly", c.gas_fixed_monthly),
        gas_dyn_monthly=n("gas_dynamic_monthly", c.gas_dyn_monthly))
    grid = GridTariff(rate=n("grid_rate", g.rate), fixed_change=n("grid_fixed_change", g.fixed_change),
                      winter=parse_profile(s.get("input_text.hb_grid_profile_winter", {}).get("state"), GRID_WINTER),
                      summer=parse_profile(s.get("input_text.hb_grid_profile_summer", {}).get("state"), GRID_SUMMER))
    return battery, contract, grid, n("battery_lifetime", 10.0)
