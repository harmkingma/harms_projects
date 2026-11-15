"""Behavioural tests for packages/ev_battery_health.yaml.

The package is loaded into a real Home Assistant core instance and the Tesla
Fleet entities are simulated with plain states, one block of state writes per
API poll, like the integration's coordinator does.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml_dict
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)
from homeassistant.util import dt as dt_util

PACKAGE = Path(__file__).resolve().parents[1] / "packages" / "ev_battery_health.yaml"
CAR = "life_the_universe_and_everything"
SOC = f"sensor.{CAR}_battery_level"
KWH = f"sensor.{CAR}_charge_energy_added"
CHARGING = f"sensor.{CAR}_charging"
ODO = f"sensor.{CAR}_odometer"
TEMP = f"sensor.{CAR}_outside_temperature"
RANGE = f"sensor.{CAR}_battery_range"
CABLE = f"binary_sensor.{CAR}_charge_cable"

MEAS = "sensor.ev_battery_health_measurement"
HIST = "sensor.ev_battery_health_history"
CAPACITY = "sensor.ev_battery_usable_capacity"
SOH = "sensor.ev_battery_soh"
CHANGE = "sensor.ev_battery_capacity_change"
LAST = "sensor.ev_battery_capacity_last_session"
RANGE_FULL = "sensor.ev_battery_range_at_100"

POLL = timedelta(minutes=10)


async def settle(hass: HomeAssistant) -> None:
    """Let queued template re-renders run.

    Template entities may defer a re-render to a timer, and the test clock is
    frozen, so timers only fire when time is advanced explicitly. Repeated so
    that sensors derived from other derived sensors settle too.
    """
    await hass.async_block_till_done()
    for _ in range(3):
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()


class Car:
    """Simulated Tesla Fleet entities."""

    def __init__(self, hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
        self.hass = hass
        self.freezer = freezer
        self.odo = 15000.0
        self.temp = 15.0

    async def poll(
        self,
        soc: float | str,
        kwh: float | str,
        charging: str = "charging",
        cable: str = "on",
        rng: float | str | None = None,
    ) -> None:
        """Write one poll's worth of states, then advance the clock."""
        self.hass.states.async_set(SOC, str(soc), {"unit_of_measurement": "%"})
        self.hass.states.async_set(KWH, str(kwh), {"unit_of_measurement": "kWh"})
        self.hass.states.async_set(CHARGING, charging)
        self.hass.states.async_set(CABLE, cable)
        self.hass.states.async_set(ODO, str(self.odo), {"unit_of_measurement": "km"})
        self.hass.states.async_set(TEMP, str(self.temp), {"unit_of_measurement": "°C"})
        if rng is not None:
            self.hass.states.async_set(RANGE, str(rng), {"unit_of_measurement": "km"})
        await settle(self.hass)
        self.freezer.tick(POLL)

    async def sleep(self) -> None:
        """Tesla Fleet entities go unknown while the car sleeps."""
        for entity in (SOC, KWH, CHARGING, CABLE, ODO, TEMP):
            self.hass.states.async_set(entity, "unknown")
        await settle(self.hass)
        self.freezer.tick(timedelta(hours=1))

    async def session(self, soc0: int, soc1: int, capacity: float) -> None:
        """Plug in, charge soc0 -> soc1 at the given true capacity, unplug."""
        await self.poll(soc0, 0.3)
        step = max(1, (soc1 - soc0) // 3)
        for soc in [*range(soc0 + step, soc1, step), soc1]:
            await self.poll(soc, round(0.3 + (soc - soc0) * capacity / 100, 2))
        await self.poll(soc1, round(0.3 + (soc1 - soc0) * capacity / 100, 2), "complete")
        await self.poll(soc1, 0, "disconnected", "off")
        self.freezer.tick(timedelta(days=1))


async def setup_package(hass: HomeAssistant) -> None:
    config = await hass.async_add_executor_job(load_yaml_dict, str(PACKAGE))
    for domain in ("input_boolean", "input_number", "template", "script", "automation"):
        assert await async_setup_component(hass, domain, {domain: config[domain]})
    await hass.async_block_till_done()
    hass.bus.async_fire("automation_reloaded")
    await hass.async_block_till_done()


def history(hass: HomeAssistant, attribute: str):
    return hass.states.get(HIST).attributes[attribute]


@pytest.fixture
async def car(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> Car:
    freezer.move_to("2026-10-01 08:00:00+00:00")
    await setup_package(hass)
    return Car(hass, freezer)


async def test_settings_initialised_once(hass: HomeAssistant, car: Car) -> None:
    assert hass.states.get("input_number.ev_bh_reference_capacity").state == "60.0"
    assert hass.states.get("input_number.ev_bh_min_soc_gain").state == "30.0"
    assert hass.states.get("input_number.ev_bh_min_outside_temp").state == "5.0"
    assert hass.states.get("input_number.ev_bh_max_days_since_full").state == "14.0"
    assert hass.states.get("input_boolean.ev_bh_initialised").state == "on"

    await hass.services.async_call(
        "input_number", "set_value",
        {"entity_id": "input_number.ev_bh_reference_capacity", "value": 57.5},
        blocking=True,
    )
    hass.bus.async_fire("automation_reloaded")
    await hass.async_block_till_done()
    assert hass.states.get("input_number.ev_bh_reference_capacity").state == "57.5"


async def test_idle_until_charging(hass: HomeAssistant, car: Car) -> None:
    # Trigger-based sensors have no state until their first trigger.
    assert hass.states.get(MEAS).state == "unknown"
    await car.poll(40, 0, "stopped")
    assert hass.states.get(MEAS).state == "idle"
    assert hass.states.get(HIST).state == "0"
    await car.poll(40, 0.2, "charging")
    assert hass.states.get(MEAS).state == "measuring"


async def test_full_session_is_accepted(hass: HomeAssistant, car: Car) -> None:
    await car.poll(30, 0.4)
    await car.poll(40, 6.4)
    await car.poll(55, 15.4)
    await car.poll(80, 30.4)
    session = hass.states.get(MEAS).attributes["session"]
    assert session["acc_soc"] == 50
    assert session["acc_kwh"] == pytest.approx(30.0)

    await car.poll(80, 30.4, "complete")
    await car.poll(80, 30.4, "disconnected", "off")

    assert hass.states.get(MEAS).state == "idle"
    assert hass.states.get(HIST).state == "1"
    sample = history(hass, "samples")[0]
    assert sample["cap"] == pytest.approx(60.0)
    assert (sample["soc0"], sample["soc1"], sample["gain"]) == (30, 80, 50)
    assert sample["odo"] == 15000
    recent = history(hass, "recent_sessions")[-1]
    assert recent["ok"] is True
    assert recent["end"] == "unplugged"
    assert hass.states.get(LAST).state == "60.0"
    # Fewer than 3 samples: no capacity estimate yet.
    assert hass.states.get(CAPACITY).state == "unknown"


async def test_solar_pause_with_counter_reset(hass: HomeAssistant, car: Car) -> None:
    await car.poll(30, 0.4)
    await car.poll(50, 12.4)
    await car.poll(50, 12.4, "stopped")
    await car.sleep()
    # Tesla starts a new charge session: the energy counter restarts at zero.
    await car.poll(52, 1.2)
    await car.poll(80, 18.0)
    session = hass.states.get(MEAS).attributes["session"]
    assert session["resets"] == 1
    await car.poll(80, 18.0, "disconnected", "off")

    sample = history(hass, "samples")[0]
    # 20 points / 12 kWh before the pause + 28 points / 16.8 kWh after it.
    assert sample["gain"] == 48
    assert sample["kwh"] == pytest.approx(28.8)
    assert sample["cap"] == pytest.approx(60.0)
    assert sample["resets"] == 1


async def test_rejections_are_recorded_with_reason(hass: HomeAssistant, car: Car) -> None:
    await car.session(70, 85, 60)
    car.temp = 2
    await car.session(30, 80, 60)
    car.temp = 15
    await car.session(30, 80, 90)

    assert hass.states.get(HIST).state == "0"
    reasons = [r["why"] for r in history(hass, "recent_sessions")]
    assert reasons[0] == "SOC gain 15 < 30 %"
    assert reasons[1] == "outside 2.0 < 5 °C"
    assert reasons[2] == "implausible 90.0 kWh"


async def test_lfp_calibration_age(hass: HomeAssistant, car: Car) -> None:
    await car.poll(100, 0, "complete")
    await car.poll(100, 0, "disconnected", "off")
    car.freezer.tick(timedelta(days=20))
    await car.session(30, 80, 60)
    car.freezer.tick(timedelta(days=1))
    await car.poll(100, 0, "complete")
    car.freezer.tick(timedelta(days=2))
    await car.session(30, 80, 60)

    old, fresh = history(hass, "recent_sessions")
    assert old["ok"] is False
    assert old["dsf"] == 20.0
    assert old["why"] == "20.0 d since 100% > 14 d"
    assert fresh["ok"] is True
    assert fresh["dsf"] == pytest.approx(2.0, abs=0.1)


async def test_session_ends_on_driving_or_soc_drop(hass: HomeAssistant, car: Car) -> None:
    await car.poll(30, 0.3)
    await car.poll(80, 30.3)
    car.odo += 25
    await car.poll(75, 30.3, "disconnected", "unknown")
    assert history(hass, "recent_sessions")[-1]["end"] == "drove"
    assert history(hass, "samples")[-1]["soc1"] == 80

    await car.poll(30, 0.3)
    await car.poll(80, 30.3, "complete")
    await car.poll(60, 30.3, "complete")
    assert history(hass, "recent_sessions")[-1]["end"] == "soc dropped"
    assert history(hass, "samples")[-1]["cap"] == pytest.approx(60.0)


async def test_trend_baseline_and_soh(hass: HomeAssistant, car: Car) -> None:
    for capacity in (59.4, 58.8, 60.0):
        await car.session(30, 80, capacity)
    assert hass.states.get(CAPACITY).state == "59.4"
    assert hass.states.get(SOH).state == "99.0"
    assert hass.states.get(CHANGE).state == "unknown"

    for capacity in (58.2, 59.4):
        await car.session(30, 80, capacity)
    assert history(hass, "baseline_kwh") == pytest.approx(59.4)
    assert hass.states.get(CHANGE).state == "0.0"

    for capacity in (57.0, 57.0, 57.0, 57.0, 57.0, 57.0):
        await car.session(30, 80, capacity)
    # Window = last 10: 58.8 60.0 58.2 59.4 57.0 x6 -> median 57.0
    assert hass.states.get(CAPACITY).state == "57.0"
    assert hass.states.get(CHANGE).state == "-4.0"
    assert hass.states.get(SOH).state == "95.0"
    assert hass.states.get(CAPACITY).attributes["window"] == 10

    await hass.services.async_call(
        "input_number", "set_value",
        {"entity_id": "input_number.ev_bh_reference_capacity", "value": 57.5},
        blocking=True,
    )
    await settle(hass)
    assert hass.states.get(SOH).state == "99.1"


async def test_discard_and_clear_history(hass: HomeAssistant, car: Car) -> None:
    await car.session(30, 80, 60)
    await car.poll(30, 0.3)
    await hass.services.async_call("script", "ev_bh_discard_measurement", blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(MEAS).state == "idle"
    assert history(hass, "recent_sessions")[-1]["end"] == "discarded"
    assert hass.states.get(HIST).state == "1"

    await hass.services.async_call("script", "ev_bh_clear_history", blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(HIST).state == "0"
    assert history(hass, "recent_sessions") == []
    assert history(hass, "baseline_kwh") is None


async def test_range_at_full(hass: HomeAssistant, car: Car) -> None:
    await car.poll(80, 0, "complete", rng=400)
    assert hass.states.get(RANGE_FULL).state == "500"
    await car.poll(40, 0, "disconnected", "off", rng=200)
    assert hass.states.get(RANGE_FULL).state == "500"
    await car.sleep()
    assert hass.states.get(RANGE_FULL).state == "500"


async def test_staggered_entity_updates(hass: HomeAssistant, car: Car) -> None:
    """States of one poll may arrive one by one; deltas must still telescope."""
    async def write(soc: float, kwh: float, charging: str = "charging", cable: str = "on") -> None:
        for entity, value in ((SOC, soc), (KWH, kwh), (CHARGING, charging), (CABLE, cable)):
            hass.states.async_set(entity, str(value))
            await settle(hass)
        car.freezer.tick(POLL)

    await write(30, 0.4)
    await write(47, 10.6)
    await write(80, 30.4)
    await write(80, 30.4, "disconnected", "off")
    assert history(hass, "samples")[0]["cap"] == pytest.approx(60.0)


async def test_history_attributes_fit_recorder_limit(hass: HomeAssistant, car: Car) -> None:
    """The recorder drops attributes larger than 16 KiB."""
    import json

    from homeassistant.helpers.json import JSONEncoder

    car.odo = 123456.0
    car.temp = -12.5
    for _ in range(55):
        await car.session(30, 80, 58.75)
    for _ in range(15):
        await car.session(70, 85, 58.75)
    attributes = dict(hass.states.get(HIST).attributes)
    assert len(attributes["samples"]) == 0
    assert len(attributes["recent_sessions"]) == 15

    await hass.services.async_call(
        "input_number", "set_value",
        {"entity_id": "input_number.ev_bh_min_outside_temp", "value": -20},
        blocking=True,
    )
    for _ in range(55):
        await car.session(30, 80, 58.75)
    for _ in range(15):
        await car.session(70, 85, 58.75)
    attributes = dict(hass.states.get(HIST).attributes)
    assert len(attributes["samples"]) == 50
    assert len(json.dumps(attributes, cls=JSONEncoder).encode()) < 16384


async def test_dashboard_templates_render(hass: HomeAssistant, car: Car) -> None:
    from homeassistant.helpers.template import Template

    dashboard = await hass.async_add_executor_job(
        load_yaml_dict, str(PACKAGE.parents[1] / "dashboard_ev_battery_health.yaml")
    )
    cards = [c.get("card", c) for c in dashboard["views"][0]["cards"]]
    markdown = {c["title"]: c["content"] for c in cards if c["type"] == "markdown"}
    gauge = next(c for c in dashboard["views"][0]["cards"] if c.get("card", {}).get("type") == "gauge")
    assert gauge["conditions"][0]["entity"] == SOH

    def render(title: str) -> str:
        return Template(markdown[title], hass).async_render(parse_result=False).strip()

    assert hass.states.get(SOH).state == "unknown"
    assert render("State of Health").startswith("**Collecting data** — 0 of 3 accepted")
    assert "at least\n30 points" in render("State of Health")
    assert "Idle" in render("Current Measurement")
    assert "No completed charging sessions yet." in render("Recent Charging Sessions")

    await car.poll(100, 0, "complete")
    await car.session(30, 80, 60)
    await car.session(70, 85, 60)
    assert render("State of Health").startswith("**Collecting data** — 1 of 3 accepted")
    await car.poll(30, 0.4)
    await car.poll(47, 10.6)
    current = render("Current Measurement")
    assert current.startswith("**Measuring** since ")
    assert "|---|---|\n| SOC | 30 % → 47 % (gain 17 points) |\n| Energy added |" in current
    assert "| Running estimate | 60.0 kWh |" in current
    assert "\n\nLast 100% charge seen: " in current

    sessions = render("Recent Charging Sessions").splitlines()
    assert sessions[0] == "| Start | SOC | Energy | Capacity | Temp | Result |"
    assert sessions[1] == "|---|---|---|---|---|---|"
    assert sessions[2].endswith("| 70→85 % | 9.0 kWh | 60.0 kWh | 15.0 °C | ❌ SOC gain 15 < 30 % |")
    assert sessions[3].endswith("| 30→80 % | 30.0 kWh | 60.0 kWh | 15.0 °C | ✅ |")
    assert len(sessions) == 4


async def test_history_survives_restart(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-10-01 08:00:00+00:00")
    samples = [
        {"t": 1, "date": "2026-09-01 08:00", "soc0": 30, "soc1": 80, "gain": 50,
         "kwh": 29.5, "cap": 59.0, "odo": 14000, "tmin": 15.0, "dsf": 1.0,
         "full": False, "resets": 0},
        {"t": 2, "date": "2026-09-08 08:00", "soc0": 30, "soc1": 80, "gain": 50,
         "kwh": 30.0, "cap": 60.0, "odo": 14300, "tmin": 15.0, "dsf": 1.0,
         "full": False, "resets": 0},
    ]
    start = int(datetime(2026, 10, 1, 7, tzinfo=UTC).timestamp())
    session = {"phase": "measuring", "start_ts": start, "last_ts": start, "start_soc": 30,
               "end_soc": 40, "prev_soc": 40, "prev_kwh": 6.3, "acc_soc": 10,
               "acc_kwh": 6.0, "start_odo": 15000.0, "tmin": 15.0, "dsf": 1.0,
               "resets": 0}
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(HIST, "2", {"samples": samples, "recent_sessions": [],
                                  "baseline_kwh": None, "baseline_date": None}),
                {"native_value": 2, "native_unit_of_measurement": None},
            ),
            (
                State(MEAS, "measuring", {"session": session, "last_full_charge_ts": None}),
                {"native_value": "measuring", "native_unit_of_measurement": None},
            ),
        ),
    )
    await setup_package(hass)
    assert hass.states.get(HIST).attributes["samples"] == samples
    assert hass.states.get(MEAS).attributes["session"]["acc_soc"] == 10

    car = Car(hass, freezer)
    car.freezer.move_to("2026-10-01 08:00:00+00:00")
    # The interrupted session continues across the restart.
    await car.poll(80, 30.3)
    await car.poll(80, 30.3, "disconnected", "off")
    assert hass.states.get(HIST).state == "3"
    assert history(hass, "samples")[-1]["cap"] == pytest.approx(60.0)
    assert hass.states.get(CAPACITY).state == "60.0"


async def test_no_template_errors(
    hass: HomeAssistant, car: Car, caplog: pytest.LogCaptureFixture
) -> None:
    await car.sleep()
    await car.session(30, 80, 60)
    await car.poll("unavailable", "unavailable", "unknown", "unavailable")
    problems = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert problems == []
