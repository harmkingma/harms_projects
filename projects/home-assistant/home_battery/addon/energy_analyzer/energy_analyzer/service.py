"""Energy Analyzer add-on main loop: nightly year simulation, results via MQTT discovery."""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import os
import pathlib
import threading
import time
import urllib.request

from .estimate import MIN_FIT_DAYS, Site, WeatherCache, fetch_weather, fit, synthesize
from .ha import PRICE_SENSOR, HomeAssistant, PriceCache, build_hours, settings_from_states
from .model import TARIFFS, Hour, price_history, price_statistics, year_summary

log = logging.getLogger("energy_analyzer")
TOPIC = "energy_analyzer"
DISCOVERY = "homeassistant"
DEVICE = {"identifiers": ["energy_analyzer"], "name": "Energy Analyzer", "manufacturer": "harms_projects",
          "model": "Home battery and contract simulation"}
SOLAR_STATISTICS = ["sensor.steca_inverter_energy_production", "sensor.steca_solar_energy", "sensor.hb_solar_energy"]
LABELS = {"fixed_2027": "Fixed 2027", "dynamic_2027": "Dynamic 2027",
          "fixed_2029": "Fixed 2029", "dynamic_2029": "Dynamic 2029"}


@dataclasses.dataclass
class Options:
    import_statistic: str = "sensor.p1_meter_energy_import"
    export_statistic: str = "sensor.p1_meter_energy_export"
    gas_statistic: str = "sensor.gas_meter_gas"
    energyzero_config_entry: str = ""
    solar_statistic: str = ""  # empty: the SOLAR_STATISTICS entry with the most history
    days: int = 365
    run_at: str = "04:15"
    estimate_missing: bool = True
    pv_kwp: float = 4.1
    pv_tilt: float = 35.0
    pv_azimuth: float = -22.0  # 0 = south, negative = east

    @classmethod
    def load(cls, path: str) -> "Options":
        try:
            raw = json.loads(pathlib.Path(path).read_text())
        except (OSError, ValueError):
            raw = {}
        names = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in names and v not in (None, "")})


def discovery_configs() -> dict[tuple[str, str], dict]:
    year = f"{TOPIC}/year"
    entities = {
        ("sensor", "status"): {"name": "Status", "state_topic": year, "value_template": "{{ value_json.status }}",
                               "json_attributes_topic": year, "icon": "mdi:chart-timeline-variant"},
        ("button", "run"): {"name": "Run simulation", "command_topic": f"{TOPIC}/run", "icon": "mdi:play"},
    }
    for t in TARIFFS:
        for k, label in (("none", "no battery"), ("battery", "battery")):
            entities[("sensor", f"{t}_{k}")] = {
                "name": f"{LABELS[t]} {label}", "state_topic": year, "unit_of_measurement": "€/yr",
                "value_template": f"{{{{ value_json.annual.{t}.{k} if value_json.annual is defined else none }}}}",
                "icon": "mdi:cash-multiple" if k == "none" else "mdi:home-battery"}
    for k in ("fixed", "dynamic"):
        entities[("sensor", f"gas_{k}")] = {
            "name": f"Gas {k}", "state_topic": year, "unit_of_measurement": "€/yr", "icon": "mdi:fire",
            "value_template": f"{{{{ value_json.gas.{k} if value_json.gas is defined else none }}}}"}
    return entities


def publish_discovery(mqtt) -> None:
    common = {"device": DEVICE, "availability_topic": f"{TOPIC}/availability"}
    for (component, key), cfg in discovery_configs().items():
        payload = {**common, **cfg, "unique_id": f"energy_analyzer_{key}",
                   "default_entity_id": f"{component}.energy_analyzer_{key}"}
        mqtt.publish(f"{DISCOVERY}/{component}/energy_analyzer/{key}/config", json.dumps(payload), retain=True)


def run(ha: HomeAssistant, opts: Options, data_dir: pathlib.Path, fetch=fetch_weather) -> dict:
    tz = ha.time_zone()
    states = ha.states()
    entry = opts.energyzero_config_entry or (states.get(PRICE_SENSOR, {}).get("attributes", {}).get("config_entry"))
    if not entry:
        return {"status": "no EnergyZero config entry",
                "detail": f"install the EnergyZero integration and the home_battery package ({PRICE_SENSOR}), "
                          "or set the energyzero_config_entry option"}
    end = dt.datetime.combine(dt.datetime.now(tz).date(), dt.time(), tz)
    start = end - dt.timedelta(days=opts.days)
    ids = {"import": opts.import_statistic, "export": opts.export_statistic, "gas": opts.gas_statistic}
    solar_ids = [opts.solar_statistic] if opts.solar_statistic else SOLAR_STATISTICS
    changes = ha.hourly_changes(list(ids.values()) + solar_ids, start, end)
    if not changes.get(ids["import"]):
        return {"status": "no import statistics", "detail": f"no hourly statistics for {ids['import']}"}
    prices = PriceCache(data_dir / "prices.json")
    # Prices for the whole window, also before the meter history starts (price history view).
    days = [start.date() + dt.timedelta(days=i) for i in range((end.date() - start.date()).days)]
    prices.fill(ha, entry, days, tz)
    measured = build_hours(changes, ids, prices, tz)
    battery, contract, grid, lifetime = settings_from_states(states)
    history = {"months": price_history(prices.electricity, prices.gas, measured, contract, tz, days[0], days[-1]),
               "fixed": contract.fixed_import, "fixed_export": round(contract.fixed_feed_in - contract.fixed_feed_in_cost, 4),
               "gas_fixed": contract.gas_fixed, "statistics": import_price_statistics(ha, prices, contract, start, end)}
    solar_id = max(solar_ids, key=lambda s: len(changes.get(s, {})))
    estimate, extra = estimate_missing(ha, opts, data_dir, tz, measured, changes, ids["import"], solar_id,
                                       prices, start, end, fetch)
    hours = sorted(measured + extra, key=lambda h: h.t)
    summary = year_summary(hours, contract, grid, battery, lifetime)
    if summary is None:
        return {"status": "waiting for 7 days of history with prices", "hours": len(hours), "price_history": history,
                "estimate": estimate}
    notes = []
    if extra:
        months = sum(1 for m in summary["months"] if m["estimated"] > 0)
        notes.append(f"{summary['days'] - summary['measured_days']} of {summary['days']} days ({months} months) "
                     f"estimated from the weather of those days")
    if summary["days"] < 330:
        notes.append(f"only {summary['days']} days of history: scaled to a year, seasons may be missing")
    if len(measured) < len(changes[ids["import"]]):
        notes.append(f"{len(changes[ids['import']]) - len(measured)} hours without a price skipped")
    return {"status": "ok", **summary, "notes": notes, "price_history": history, "estimate": estimate,
            "settings": {"battery": dataclasses.asdict(battery), "lifetime_years": lifetime,
                         "statistics": {**ids, "solar": solar_id}}}


def estimate_missing(ha, opts: Options, data_dir: pathlib.Path, tz, measured: list[Hour], changes: dict,
                     import_id: str, solar_id: str, prices: PriceCache, start: dt.datetime, end: dt.datetime,
                     fetch) -> tuple[dict, list[Hour]]:
    """Estimated hours for the window's hours without meter data (see estimate.py), with a status block."""
    if not opts.estimate_missing:
        return {"status": "off"}, []
    solar = changes.get(solar_id, {})
    if not solar:
        return {"status": f"no solar statistics ({solar_id})"}, []
    try:
        config = ha.config()
        site = Site(config["latitude"], config["longitude"], opts.pv_tilt, opts.pv_azimuth, opts.pv_kwp)
        weather = WeatherCache(data_dir / "weather.json", site)
        weather.fill(start.date(), (end - dt.timedelta(days=1)).date(), tz, fetch)
    except Exception as err:  # noqa: BLE001 - the year simulation still runs on measured data
        log.warning("weather download failed: %s", err)
        return {"status": f"weather download failed: {err}"}, []
    model = fit(measured, solar, weather.hours, tz, site)
    if model is None:
        return {"status": f"waiting for {MIN_FIT_DAYS} full days with meter, solar and weather data"}, []
    have = changes[import_id]
    missing = [ts for ts in range(int(start.timestamp()), int(end.timestamp()), 3600) if ts not in have]
    extra = synthesize(model, missing, weather.hours, prices.electricity, prices.gas, tz, site)
    return {"status": "ok", "estimated_hours": len(extra), "model": model.summary(),
            "site": {"tilt": site.tilt, "azimuth": site.azimuth, "kwp": site.kwp}}, extra

STATISTICS = {"electricity_dynamic": ("Dynamic electricity price (all-in)", "€/kWh"),
              "electricity_fixed": ("Fixed electricity price", "€/kWh"),
              "gas_dynamic": ("Dynamic gas price (all-in)", "€/m³"),
              "gas_fixed": ("Fixed gas price", "€/m³")}


def import_price_statistics(ha: HomeAssistant, prices: PriceCache, contract, start: dt.datetime,
                            end: dt.datetime) -> str:
    """Hourly all-in prices as HA statistics (energy_analyzer:*); a failure only disables the graphs."""
    try:
        series = price_statistics(prices.electricity, prices.gas, contract, start.timestamp(), end.timestamp())
        for key, (name, unit) in STATISTICS.items():
            if series[key]:
                ha.import_statistics(key, name, unit, series[key])
        return "ok"
    except Exception as err:  # noqa: BLE001
        log.warning("importing price statistics failed: %s", err)
        return f"failed: {err}"


def next_run(tz, at: str) -> float:
    hour, minute = (int(v) for v in at.split(":"))
    now = dt.datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (target if target > now else target + dt.timedelta(days=1)).timestamp()


def supervisor_mqtt() -> dict:
    req = urllib.request.Request("http://supervisor/services/mqtt",
                                 headers={"Authorization": f"Bearer {os.environ['SUPERVISOR_TOKEN']}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)["data"]


def main() -> None:
    import paho.mqtt.client as paho

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    opts = Options.load(os.environ.get("ENERGY_ANALYZER_OPTIONS", "/data/options.json"))
    data_dir = pathlib.Path(os.environ.get("ENERGY_ANALYZER_DATA", "/data"))
    token = os.environ.get("SUPERVISOR_TOKEN") or os.environ["HA_TOKEN"]
    if "SUPERVISOR_TOKEN" in os.environ:
        ha = HomeAssistant("http://supervisor/core/api", "ws://supervisor/core/websocket", token)
        broker = supervisor_mqtt()
    else:
        url = os.environ.get("HA_URL", "http://homeassistant.local:8123")
        ha = HomeAssistant(f"{url}/api", url.replace("http", "ws", 1) + "/api/websocket", token)
        broker = {"host": os.environ.get("MQTT_HOST", "localhost"), "port": int(os.environ.get("MQTT_PORT", 1883)),
                  "username": os.environ.get("MQTT_USER"), "password": os.environ.get("MQTT_PASSWORD")}
    wake = threading.Event()
    client = paho.Client(paho.CallbackAPIVersion.VERSION2, client_id="energy_analyzer")

    def on_connect(c, userdata, flags, reason_code, properties):
        log.info("MQTT connected (%s)", reason_code)
        publish_discovery(c)
        c.publish(f"{TOPIC}/availability", "online", retain=True)
        c.subscribe(f"{TOPIC}/run")

    client.on_connect = on_connect
    client.on_message = lambda c, u, msg: wake.set()
    if broker.get("username"):
        client.username_pw_set(broker["username"], broker.get("password"))
    client.will_set(f"{TOPIC}/availability", "offline", retain=True)
    client.connect_async(broker["host"], int(broker["port"]))
    client.loop_start()

    wake.wait(120)  # let Home Assistant finish starting
    while True:
        wake.clear()
        t0 = time.monotonic()
        try:
            result = run(ha, opts, data_dir)
            retry = None
        except Exception as err:  # noqa: BLE001 - report and retry
            log.exception("simulation failed")
            result, retry = {"status": "error", "detail": str(err)}, time.time() + 3600
        result["last_run"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        result["run_seconds"] = round(time.monotonic() - t0, 1)
        client.publish(f"{TOPIC}/year", json.dumps(result), retain=True)
        log.info("simulation %s in %ss, best %s", result["status"], result["run_seconds"], result.get("best"))
        target = retry or next_run(ha.time_zone(), opts.run_at)
        wake.wait(max(target - time.time(), 60))


if __name__ == "__main__":
    main()
