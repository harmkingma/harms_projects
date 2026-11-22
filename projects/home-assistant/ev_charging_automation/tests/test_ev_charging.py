"""Behavioural tests for packages/ev_charging.yaml.

The package runs in a real Home Assistant core instance. The Tesla and the
Alfen are simulated by states plus service handlers that react like the real
devices: the Alfen select confirms a mode, and the Tesla amps setting rejects
values above the 'max' the car reports, which follows the charger's offer.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml_dict
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

PACKAGE = Path(__file__).resolve().parents[1] / "packages" / "ev_charging.yaml"
CAR = "life_the_universe_and_everything"
SOC = f"sensor.{CAR}_battery_level"
ODO = f"sensor.{CAR}_odometer"
KWH = f"sensor.{CAR}_charge_energy_added"
AMPS = f"number.{CAR}_charge_current"
LIMIT = f"number.{CAR}_charge_limit"
SWITCH = f"switch.{CAR}_charge"
MODE = "select.ev_charger_solar_charging_mode"
STATUS = "sensor.ev_charger_status_code_socket_1_2"
OFFER = {"Disable": 16, "Comfort": 6, "Green": 0}


async def pump(hass: HomeAssistant) -> None:
    # Scripts sit in delays, so block_till_done would wait forever; yield instead.
    for _ in range(200):
        await asyncio.sleep(0)


class Home:
    def __init__(self, hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
        self.hass, self.freezer = hass, freezer
        self.calls: list[tuple[str, str, object]] = []
        self.mode_works = True
        self.notifications = async_mock_service(hass, "persistent_notification", "create")
        async_mock_service(hass, "logbook", "log")
        async_mock_service(hass, "homeassistant", "update_entity")
        async_mock_service(hass, "button", "press")
        hass.services.async_register("select", "select_option", self._select)
        hass.services.async_register("number", "set_value", self._number)
        hass.services.async_register("switch", "turn_on", self._switch)
        hass.services.async_register("switch", "turn_off", self._switch)

    def set(self, entity_id: str, state: object, **attributes) -> None:
        current = self.hass.states.get(entity_id)
        attrs = {**(current.attributes if current else {}), **attributes}
        self.hass.states.async_set(entity_id, str(state), attrs)

    async def _select(self, call: ServiceCall) -> None:
        option = call.data["option"]
        self.calls.append(("mode", call.data["entity_id"][0], option))
        if self.mode_works:
            self.set(MODE, option)
            # The car sees the new pilot signal and reports it as its amps maximum.
            self.set(AMPS, min(float(self.hass.states.get(AMPS).state), OFFER[option]), max=OFFER[option])

    async def _number(self, call: ServiceCall) -> None:
        entity_id, value = call.data["entity_id"][0], call.data["value"]
        if value > self.hass.states.get(entity_id).attributes["max"]:
            raise ServiceValidationError(f"{value} above max for {entity_id}")
        self.calls.append(("number", entity_id, value))
        self.set(entity_id, value)

    async def _switch(self, call: ServiceCall) -> None:
        self.calls.append((call.service, SWITCH, None))
        self.set(SWITCH, "on" if call.service == "turn_on" else "off")

    def actions(self, kind: str, entity_id: str) -> list[object]:
        return [value for k, e, value in self.calls if k == kind and e == entity_id]

    def index(self, kind: str, entity_id: str, value: object = None) -> int:
        return next(i for i, c in enumerate(self.calls) if c[:2] == (kind, entity_id) and value in (None, c[2]))

    def charging(self, amps: float, status: str = "Charging Normal") -> None:
        self.set(STATUS, status)
        for phase in (1, 2, 3):
            self.set(f"sensor.ev_charger_current_l{phase}_socket_1", amps)

    async def advance(self, seconds: float, step: float = 5) -> None:
        end = dt_util.utcnow() + timedelta(seconds=seconds)
        while dt_util.utcnow() < end:
            target = min(end, dt_util.utcnow() + timedelta(seconds=step))
            async_fire_time_changed(self.hass, target)
            self.freezer.move_to(target)
            await pump(self.hass)

    async def set_helper(self, entity_id: str, value: object) -> None:
        domain = entity_id.split(".")[0]
        if domain == "input_number":
            await self.hass.services.async_call(domain, "set_value", {"entity_id": entity_id, "value": value}, blocking=True)
        elif domain == "input_boolean":
            await self.hass.services.async_call(domain, "turn_on" if value else "turn_off", {"entity_id": entity_id}, blocking=True)
        else:
            await self.hass.services.async_call(domain, "set_datetime", {"entity_id": entity_id, **value}, blocking=True)


@pytest.fixture
async def home(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> Home:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    # Monday 23 Nov 2026, 04:00 local: before the planned night start.
    freezer.move_to("2026-11-23 03:00:30+00:00")
    h = Home(hass, freezer)
    h.set(SOC, 40, unit_of_measurement="%")
    h.set(AMPS, 6, min=0, max=6)
    h.set(LIMIT, 80, min=50, max=100)
    h.set(SWITCH, "off")
    h.set(MODE, "Comfort", options=["Disable", "Comfort", "Green"])
    h.set("number.ev_charger_max_station_current", 16, min=0, max=16)
    h.charging(0, "Wait Vehicle Charging")
    for phase in (1, 2, 3):
        h.set(f"sensor.p1_meter_power_phase_{phase}", 300, unit_of_measurement="W")
    h.set("sensor.p1_power_mean_10min", 500)
    h.set("sensor.steca_inverter_ac_power", 0)

    config = await hass.async_add_executor_job(load_yaml_dict, str(PACKAGE))
    for domain in ("input_boolean", "input_number", "input_datetime", "counter"):
        assert await async_setup_component(hass, domain, {domain: config[domain]})
    await hass.async_block_till_done()
    # Helpers first, so the automations never see their unset minimums.
    for entity_id, value in {
        "input_number.ev_roundtrip_consumption": 33, "input_number.ev_regular_charge_limit": 80,
        "input_number.ev_min_remaining_soc": 25, "input_number.ev_min_safe_soc": 30,
        "input_number.ev_max_power_charge_rate": 15, "input_number.ev_ready_margin_hours": 1,
        "input_number.ev_conditioning_interval_days": 14, "input_boolean.work_monday": True,
        "input_datetime.work_departure_time": {"time": "07:30:00"},
        "input_datetime.ev_last_full_charge": {"datetime": "2026-11-20 05:00:00"},
    }.items():
        await h.set_helper(entity_id, value)
    for domain in ("template", "script", "automation"):
        assert await async_setup_component(hass, domain, {domain: config[domain]})
    await hass.async_block_till_done()
    hass.bus.async_fire("automation_reloaded")
    await hass.async_block_till_done()
    # Template entities may defer a re-render to a timer on the frozen clock.
    for _ in range(3):
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
    return h


def state(hass: HomeAssistant, entity_id: str) -> str:
    return hass.states.get(entity_id).state


async def test_waiting_night_session_holds_green_and_starts_in_disable_before_charging(
    hass: HomeAssistant, home: Home
) -> None:
    # Required 25 + 33 = 58 %, deficit 18 % at 15 %/h plus 1 h margin: start 05:18.
    assert state(hass, "sensor.ev_required_soc") == "58"
    assert state(hass, "binary_sensor.ev_night_session_pending") == "on"

    await home.advance(5 * 60)
    assert state(hass, MODE) == "Green"
    assert state(hass, SWITCH) == "off"

    await home.advance(80 * 60)
    assert state(hass, "input_boolean.ev_night_session") == "on"
    assert state(hass, MODE) == "Disable"
    assert state(hass, SWITCH) == "on"
    mode_set = home.index("mode", MODE, "Disable")
    assert mode_set < home.index("number", AMPS, 16) < home.index("number", LIMIT, 58) < home.index("turn_on", SWITCH)
    # No stop between holding and starting.
    assert home.actions("turn_off", SWITCH) == []


async def test_unconfirmed_mode_aborts_start_and_notifies(hass: HomeAssistant, home: Home) -> None:
    home.mode_works = False
    await home.set_helper("input_boolean.ev_hold_green_while_waiting", False)
    await home.advance(85 * 60)

    assert home.actions("turn_on", SWITCH) == []
    assert home.actions("number", LIMIT) == []
    # Three attempts per start; the night start retries on its next tick.
    assert len(home.actions("mode", MODE)) > 3
    assert any(c.data["notification_id"] == "ev_charger_mode" for c in home.notifications)


async def test_hold_off_returns_to_comfort_for_app_charging(hass: HomeAssistant, home: Home) -> None:
    await home.advance(5 * 60)
    assert state(hass, MODE) == "Green"  # the hold is on by default

    home.calls.clear()
    await home.set_helper("input_boolean.ev_hold_green_while_waiting", False)
    await home.advance(10 * 60)
    assert state(hass, MODE) == "Comfort"
    assert home.actions("mode", MODE) == ["Comfort"]


async def start_running_night_session(hass: HomeAssistant, home: Home, amps: float) -> None:
    await home.advance(85 * 60)
    assert state(hass, SWITCH) == "on"
    home.calls.clear()
    # Tesla lowered its own setting; the charger still offers 16 A.
    home.set(AMPS, amps, max=16)
    home.charging(amps)


async def test_watchdog_raises_lowered_car_amps(hass: HomeAssistant, home: Home) -> None:
    await start_running_night_session(hass, home, 5)
    await home.advance(5 * 60)

    assert home.actions("number", AMPS) == [16]
    assert state(hass, "counter.ev_watchdog_corrections") == "1"
    assert any(c.data["notification_id"] == "ev_charge_watchdog" for c in home.notifications)


async def test_watchdog_waits_out_load_balancing_then_escalates_once_per_step(
    hass: HomeAssistant, home: Home
) -> None:
    await start_running_night_session(hass, home, 16)
    home.charging(5.1, "Load Balancing Limited")
    await home.advance(30 * 60)
    assert state(hass, "binary_sensor.ev_current_shortfall") == "off"
    assert home.calls == []

    home.charging(5.1)
    await home.advance(20 * 60)
    assert home.actions("number", AMPS) == [15, 16]
    assert home.actions("turn_off", SWITCH) == []

    await home.advance(15 * 60)
    assert home.actions("turn_off", SWITCH) == [None]
    assert home.actions("turn_on", SWITCH) == [None]
    assert state(hass, "counter.ev_watchdog_corrections") == "2"


async def test_watchdog_ignores_shortfall_when_fuse_is_full(hass: HomeAssistant, home: Home) -> None:
    await start_running_night_session(hass, home, 16)
    home.charging(8)
    for phase in (1, 2, 3):
        home.set(f"sensor.p1_meter_power_phase_{phase}", 5000)  # 21.7 A, room 25 - 21.7 + 8 = 11.3 A
    await home.advance(30 * 60)

    assert state(hass, "binary_sensor.ev_current_shortfall") == "off"
    assert home.calls == []


async def test_consumption_learned_from_drives_replaces_manual_value(hass: HomeAssistant, home: Home) -> None:
    async def poll(odo: float, soc: int, kwh: float) -> None:
        home.set(ODO, odo, unit_of_measurement="km")
        home.set(SOC, soc)
        home.set(KWH, kwh, unit_of_measurement="kWh")
        await home.advance(6 * 60, step=30)

    await poll(1000, 60, 4.0)
    await poll(1031, 52, 4.0)       # drive: 31 km, 8 %
    await poll(1062.5, 44, 4.0)     # drive: 31.5 km, 8 %
    await poll(1062.5, 43, 4.0)     # parked drain: not consumption
    await poll(1100, 40, 2.0)       # charged on the way (new session resets the counter): skipped
    await poll(1137, 31, 2.0)       # drive: 37 km, 9 %

    history = hass.states.get("sensor.ev_consumption_history")
    assert float(history.state) == 99.5
    assert float(history.attributes["soc_used"]) == 25
    assert state(hass, "sensor.ev_consumption_rate") == "unavailable"
    assert hass.states.get("sensor.ev_roundtrip_consumption_effective").attributes["source"] == "manual"

    await poll(1141, 30, 2.0)       # 103.5 km, 26 %
    assert float(state(hass, "sensor.ev_consumption_rate")) == round(26 / 103.5 * 100, 2)
    effective = hass.states.get("sensor.ev_roundtrip_consumption_effective")
    assert effective.attributes["source"] == "learned"
    assert float(effective.state) == round(26 / 103.5 * 125 * 1.01, 1)
    assert state(hass, "sensor.ev_required_soc") == str(round(25 + float(effective.state)))

    hass.bus.async_fire("ev_consumption_command", {"command": "seed", "km": 500, "soc": 120})
    await home.advance(60)
    # The window keeps the newest segments that cover 500 km: just the seed.
    assert float(state(hass, "sensor.ev_consumption_history")) == 500
    assert float(state(hass, "sensor.ev_consumption_rate")) == 24.0
