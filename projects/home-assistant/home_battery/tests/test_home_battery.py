"""Behavioural tests for packages/home_battery.yaml.

The package runs in a real Home Assistant core instance. The HomeWizard P1 counters are plain
states advanced minute by minute; EnergyZero is a mocked get_energy_prices action plus a
registry entry, so config_entry_id() resolves.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml_dict
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

PACKAGE = Path(__file__).resolve().parents[1] / "packages" / "home_battery.yaml"
IMPORT, EXPORT = "sensor.p1_meter_energy_import", "sensor.p1_meter_energy_export"
TARIFFS = ("fixed_2027", "dynamic_2027", "fixed_2029", "dynamic_2029")


def market(hour: int) -> float:
    return 0.05 if hour < 6 else 0.35 if 17 <= hour < 21 else 0.15


def num(hass: HomeAssistant, entity_id: str, attribute: str | None = None) -> float:
    state = hass.states.get(entity_id)
    return float(state.attributes[attribute] if attribute else state.state)


class House:
    def __init__(self, hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
        self.hass, self.freezer = hass, freezer
        self.imp, self.exp = 1000.0, 500.0

    def meters(self) -> None:
        self.hass.states.async_set(IMPORT, f"{self.imp:.4f}", {"unit_of_measurement": "kWh"})
        self.hass.states.async_set(EXPORT, f"{self.exp:.4f}", {"unit_of_measurement": "kWh"})

    async def run(self, minutes: int, import_kw: float = 0.0, export_kw: float = 0.0) -> None:
        for _ in range(minutes):
            self.imp += import_kw / 60
            self.exp += export_kw / 60
            self.meters()
            target = dt_util.utcnow() + timedelta(minutes=1)
            async_fire_time_changed(self.hass, target)
            self.freezer.move_to(target)
            await self.hass.async_block_till_done()


@pytest.fixture
async def house(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> House:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-01-11 23:00:00+00:00")  # 00:00 local, Monday 12 January
    entry = MockConfigEntry(domain="energyzero")
    entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create("sensor", "energyzero", "current_price", config_entry=entry,
                                           suggested_object_id="energyzero_today_energy_current_hour_price")
    midnight = dt_util.start_of_local_day()
    quarters = [{"timestamp": (midnight + timedelta(minutes=15 * i)).isoformat(), "price": market((i // 4) % 24)}
                for i in range(2 * 96)]
    calls = async_mock_service(hass, "energyzero", "get_energy_prices", response={"prices": quarters},
                               supports_response=SupportsResponse.ONLY)
    config = await hass.async_add_executor_job(load_yaml_dict, str(PACKAGE))
    for domain in ("input_boolean", "input_number", "input_text", "input_datetime", "template", "script",
                   "automation", "sensor", "utility_meter"):
        assert await async_setup_component(hass, domain, {domain: config[domain]})
    await hass.async_block_till_done()
    hass.bus.async_fire("automation_reloaded")
    hass.bus.async_fire("event_template_reloaded")
    await hass.async_block_till_done()
    assert calls and calls[0].data["interval"] == "quarter"
    # One whole local day per call (the service fetches start..end inclusive).
    assert calls[0].data["start"] == calls[0].data["end"] == "2026-01-12"
    assert calls[1].data["start"] == calls[1].data["end"] == "2026-01-13"
    h = House(hass, freezer)
    h.meters()
    return h


async def test_price_list_is_stored_per_quarter(hass: HomeAssistant, house: House) -> None:
    prices = hass.states.get("sensor.hb_electricity_prices")
    assert len(prices.attributes["prices"]) == 192  # today and tomorrow returned twice, deduplicated
    assert prices.attributes["step_s"] == 900
    assert prices.attributes["start_ts"] == dt_util.start_of_local_day().timestamp()
    assert prices.attributes["prices"][17 * 4] == 0.35


async def test_winter_night_costs_and_dynamic_battery_grid_charging(hass: HomeAssistant, house: House) -> None:
    await house.run(1)  # first tick only reads the counters
    await house.run(150, import_kw=0.6)
    imported = 150 * 0.6 / 60
    assert num(hass, "sensor.hb_cost_fixed_2027_no_battery", "import_kwh") == pytest.approx(imported, abs=1e-3)
    assert num(hass, "sensor.hb_cost_fixed_2027_no_battery") == pytest.approx(imported * 0.27, abs=1e-3)
    assert num(hass, "sensor.hb_cost_dynamic_2027_no_battery") == pytest.approx(imported * (0.05 + 0.1265), abs=1e-3)
    # 2029 winter night weight 0.48 x 0.17 on top.
    assert num(hass, "sensor.hb_cost_fixed_2029_no_battery") == pytest.approx(imported * (0.27 + 0.0816), abs=1e-3)
    # Flat fixed price and no surplus: the battery does nothing but its standby.
    assert num(hass, "sensor.hb_cost_fixed_2027_battery", "grid_charge_kwh") == 0
    assert num(hass, "sensor.hb_battery_soc_fixed_2027") == 0
    # Cheapest quarters of the night: the dynamic battery fills from the grid and holds it.
    dyn = hass.states.get("sensor.hb_cost_dynamic_2027_battery").attributes
    assert dyn["grid_charge_kwh"] == pytest.approx(5 / 0.85 ** 0.5, abs=0.01)
    assert dyn["discharge_kwh"] == 0
    assert num(hass, "sensor.hb_battery_soc_dynamic_2027") == pytest.approx(100, abs=0.1)
    # Evening peak: the stored energy covers the import.
    house.freezer.move_to(dt_util.start_of_local_day() + timedelta(hours=17, minutes=1))
    await house.run(1)
    await house.run(60, import_kw=0.6)
    dyn = hass.states.get("sensor.hb_cost_dynamic_2027_battery").attributes
    assert dyn["discharge_kwh"] == pytest.approx(0.6, abs=0.02)
    assert num(hass, "sensor.hb_tracking_days") > 0


async def test_surplus_is_stored_and_reset_clears_totals(hass: HomeAssistant, house: House) -> None:
    house.freezer.move_to(dt_util.start_of_local_day() + timedelta(hours=12))
    await house.run(1)
    await house.run(30, export_kw=3.0)
    fixed = hass.states.get("sensor.hb_cost_fixed_2027_battery").attributes
    # 2.4 kW battery power; the rest is still exported.
    assert fixed["solar_charge_kwh"] == pytest.approx(30 * 2.4 / 60, abs=1e-3)
    assert fixed["export_kwh"] == pytest.approx(30 * 0.6 / 60, abs=1e-3)
    assert num(hass, "sensor.hb_cost_fixed_2027_no_battery") == pytest.approx(-1.5 * 0.03, abs=1e-3)
    await hass.services.async_call("script", "hb_reset_statistics", blocking=True)
    await hass.async_block_till_done()
    assert num(hass, "sensor.hb_cost_fixed_2027_battery") == 0
    assert num(hass, "sensor.hb_cost_fixed_2027_battery", "solar_charge_kwh") == 0
    assert hass.states.get("sensor.hb_simulation_state").attributes["soc"] == {}


async def test_ev_energy_adds_up_over_sessions(hass: HomeAssistant, house: House) -> None:
    ev = "sensor.life_the_universe_and_everything_charge_energy_added"
    for value in ("2.0", "unknown", "5.5", "0.0", "3.0"):
        hass.states.async_set(ev, value)
        await hass.async_block_till_done()
    assert num(hass, "sensor.hb_ev_charged_energy") == pytest.approx(8.5)


async def test_projection_scales_a_week_to_a_year_with_fees(hass: HomeAssistant, house: House) -> None:
    week = {t: {"none": 10.0, "battery": 6.0, "imp": 20.0, "exp": 5.0, "sc": 4.0, "gc": 1.0, "dis": 4.25, "soc": 1.0}
            for t in TARIFFS}
    hass.bus.async_fire("home_battery_tick", {
        "ts": dt_util.utcnow().timestamp(), "minutes": 7 * 1440, "import": 1, "export": 1, "gas": 1, "market": 0.1,
        "gas_market": 0.4, "price_gap": False, "d_imp": 30.0, "d_exp": 5.0, "d_gas": 7.0, "sim": week,
        "soc": {t: 1.0 for t in TARIFFS}, "gas_cost": {"fixed": 12.0, "dynamic": 10.0}, "neg": {"kwh": 0, "cost": 0},
        "hour": 0, "hour_export": 0, "profile": [0] * 24, "surplus": 0, "load_kw": 0.4})
    await hass.async_block_till_done()
    for _ in range(3):  # template updates are scheduled, not immediate
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
    projection = hass.states.get("sensor.hb_live_projection")
    f = 365 / 7
    assert projection.attributes["annual"]["fixed_2027"] == {"none": round(10 * f + 84), "battery": round(6 * f + 84)}
    assert projection.attributes["annual"]["dynamic_2029"]["none"] == round(10 * f + 84 - 240)
    bat = projection.attributes["battery"]["dynamic_2027"]
    assert bat["saving"] == round(4 * f) and bat["payback"] == round(3000 / (4 * f), 1)
    assert bat["cycles"] == round(4.25 * f / 0.85 ** 0.5 / 5)
    assert projection.attributes["gas"]["fixed"] == round(12 * f + 84)
    assert projection.state == "fixed_2027_battery"  # equal costs: the first option wins
    assert num(hass, "sensor.hb_battery_soc_dynamic_2029") == 20.0


async def test_dashboard_markdown_renders_with_live_and_year_data(hass: HomeAssistant, house: House) -> None:
    from energy_analyzer.model import Battery, Contract, GridTariff, Hour, price_history, year_summary
    from homeassistant.helpers.template import Template

    await house.run(1)
    await house.run(60, import_kw=0.5)
    start = dt_util.start_of_local_day()
    hours = [Hour(t=start + timedelta(hours=i), imp=0.5, exp=1.0 if 11 <= (i % 24) < 15 else 0.0,
                  market=market(i % 24), gas=0.1, gas_market=0.4) for i in range(14 * 24)]
    year = year_summary(hours, Contract(), GridTariff(), Battery())
    electricity = {int(h.t.timestamp()): h.market for h in hours}
    gas = {int(start.timestamp()): 0.9}
    history = {"months": price_history(electricity, gas, hours, Contract(), start.tzinfo, start.date(),
                                       (start + timedelta(days=13)).date()),
               "fixed": 0.27, "fixed_export": 0.03, "gas_fixed": 1.72, "statistics": "ok"}
    hass.states.async_set("sensor.energy_analyzer_status", "ok",
                          {**year, "notes": ["test"], "last_run": "2026-01-12T03:00:00+00:00", "price_history": history})
    dashboard = load_yaml_dict(str(PACKAGE.parents[1] / "dashboard_home_battery.yaml"))
    cards = [c for v in dashboard["views"] for c in v["cards"] if c["type"] == "markdown"]
    rendered = {c["title"]: Template(c["content"], hass).async_render(parse_result=False) for c in cards}
    assert len(rendered) == 7
    for title, text in rendered.items():
        assert "Waiting" not in text and "No prices" not in text, title
    verdict = rendered["Verdict"]
    assert "year simulation" in verdict and "### 2029" in verdict and "payback" in verdict
    assert "Only 14 days of meter history" in verdict
    model = {"use_error_pct": 8.1, "solar_error_pct": 12.0, "fit_days": 14, "base_kwh_day": 9.0,
             "heating_kwh_per_degree_day": 1.2, "cooling_kwh_per_degree_day": 0.8, "solar_kwh_per_kwh_m2": 3.4,
             "gas_base_m3_day": 0.5, "gas_m3_per_degree_day": 0.2}
    hass.states.async_set("sensor.energy_analyzer_status", "ok", {
        **hass.states.get("sensor.energy_analyzer_status").attributes, "days": 365,
        "estimate": {"status": "ok", "model": model, "site": {"kwp": 4.1, "tilt": 35, "azimuth": -22}}})
    for card in cards:
        Template(card["content"], hass).async_render(parse_result=False)
    verdict = Template(next(c for c in cards if c["title"] == "Verdict")["content"], hass).async_render(parse_result=False)
    assert "other 351 days" in verdict and "±8.1 %" in verdict
    months = rendered["Dynamic vs fixed per month"]
    assert "| 2026-01 |" in months and "cheaper than fixed in 0 of 1 months" in months
