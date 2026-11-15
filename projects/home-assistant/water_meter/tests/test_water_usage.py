"""Behavioural tests for packages/water_usage.yaml.

The package runs in a real Home Assistant core instance. The Water Meter Reader
add-on is simulated by its MQTT draw messages (water_meter/draw), the gas meter
and the bathroom humidity detection by plain states.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml_dict
from pytest_homeassistant_custom_component.common import (
    async_fire_mqtt_message,
    async_fire_time_changed,
    async_mock_service,
)

PACKAGE = Path(__file__).resolve().parents[1] / "packages" / "water_usage.yaml"
GAS = "sensor.gas_meter_gas"
DETECTED = "input_datetime.bathroom_shower_detected"


async def settle(hass: HomeAssistant) -> None:
    await hass.async_block_till_done()
    for _ in range(3):
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()


def iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def num(hass: HomeAssistant, entity_id: str, attribute: str | None = None) -> float:
    state = hass.states.get(entity_id)
    return float(state.attributes[attribute] if attribute else state.state)


class House:
    def __init__(self, hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
        self.hass, self.freezer = hass, freezer
        self.logbook = async_mock_service(hass, "logbook", "log")

    async def wait(self, minutes: float) -> None:
        target = dt_util.utcnow() + timedelta(minutes=minutes)
        # Loop timers (the gas settle delay) only fire for a time ahead of the frozen clock.
        async_fire_time_changed(self.hass, target)
        self.freezer.move_to(target)
        await settle(self.hass)

    def gas(self, m3: float) -> None:
        self.hass.states.async_set(GAS, f"{m3:.3f}", {"unit_of_measurement": "m³"})

    def humid_shower(self) -> None:
        self.hass.states.async_set(DETECTED, iso(dt_util.now()), {"timestamp": dt_util.utcnow().timestamp()})

    async def draw(self, event: str, **payload) -> None:
        async_fire_mqtt_message(self.hass, "water_meter/draw", json.dumps({"event": event, **payload}))
        # No block_till_done: after an end message the automation sits in its gas settle delay.
        for _ in range(20):
            await asyncio.sleep(0)


def end_payload(start: datetime, main_l: float, main_min: float, side_l: float = 0, side_min: float = 0,
                complete: bool = True) -> dict:
    main_end = start + timedelta(minutes=main_min)
    end = main_end + timedelta(minutes=side_min + (1 if side_l else 0))
    return {
        "start": iso(start), "end": iso(end), "volume_l": main_l + side_l,
        "duration_min": round((end - start).total_seconds() / 60, 2), "flowing_min": main_min + side_min,
        "main_start": iso(start), "main_end": iso(main_end), "main_volume_l": main_l,
        "main_duration_min": main_min, "main_flowing_min": main_min,
        "main_flow": round(main_l / main_min, 2), "level_flow": round(main_l / main_min, 2), "peak_flow": 9.9,
        "side_volume_l": side_l, "side_flowing_min": side_min, "complete": complete, "readings": 30,
    }


@pytest.fixture
async def house(hass: HomeAssistant, freezer: FrozenDateTimeFactory, mqtt_mock) -> House:
    freezer.move_to("2026-11-05 05:30:00+00:00")
    config = await hass.async_add_executor_job(load_yaml_dict, str(PACKAGE))
    for domain in ("input_boolean", "input_number", "input_datetime", "template", "automation"):
        assert await async_setup_component(hass, domain, {domain: config[domain]})
    await hass.async_block_till_done()
    hass.bus.async_fire("automation_reloaded")
    await hass.async_block_till_done()
    h = House(hass, freezer)
    h.gas(1000.0)
    hass.states.async_set("sensor.gas_rate", "0.0")
    hass.states.async_set(DETECTED, "2026-11-01 00:00:00", {"timestamp": 0})
    hass.states.async_set("input_boolean.bathroom_shower_session", "off")
    return h


async def test_shower_uses_main_run_and_counts_side_water_as_tap(hass: HomeAssistant, house: House) -> None:
    water_start = dt_util.utcnow() - timedelta(seconds=25)
    await house.draw("start", after=iso(water_start), seen=iso(dt_util.utcnow()))
    await house.wait(3)
    house.humid_shower()
    await house.wait(15)
    house.gas(1000.3)
    await house.wait(7)
    await house.draw("end", **end_payload(water_start, 138.9, 18.31, side_l=2.6, side_min=2.93))
    await house.wait(10)  # gas settle time

    last = hass.states.get("sensor.water_last_draw")
    assert last.state == "shower"
    assert last.attributes["volume_l"] == 138.9 and last.attributes["flowing_min"] == 18.31
    assert last.attributes["side_category"] == "tap" and last.attributes["side_volume_l"] == 2.6
    assert num(hass, "sensor.water_shower_total") == 138.9
    assert num(hass, "sensor.water_shower_total", "flowing_min") == 18.31
    assert num(hass, "sensor.water_shower_average_flow") == 7.6
    assert num(hass, "sensor.water_tap_total") == 2.6
    assert num(hass, "sensor.water_tap_total", "flowing_min") == 2.93
    assert num(hass, "sensor.water_toilet_total") == 0
    assert num(hass, "sensor.water_shower_count") == 1
    assert num(hass, "sensor.gas_shower_total") == pytest.approx(0.3)
    assert num(hass, "sensor.hot_water_demand_total") == 138.9
    message = house.logbook[-1].data["message"]
    assert "water ran 18.31 of 18.31 min" in message and "plus 2.6 L tap water" in message


async def test_missed_start_message_skips_gas_but_keeps_water(hass: HomeAssistant, house: House) -> None:
    water_start = dt_util.utcnow()
    await house.wait(2)
    house.gas(1000.5)  # space heating; no start message, so no gas start known
    await house.draw("end", **end_payload(water_start, 7.6, 1.75))
    await house.wait(10)
    assert hass.states.get("sensor.water_last_draw").state == "toilet"
    assert num(hass, "sensor.water_toilet_total") == 7.6
    assert num(hass, "sensor.gas_hot_water_total") == 0
    assert "start missed" in house.logbook[-1].data["message"]


async def test_reading_gap_counts_volume_but_not_flow_time(hass: HomeAssistant, house: House) -> None:
    water_start = dt_util.utcnow()
    await house.draw("start", after=iso(water_start), seen=iso(water_start))
    await house.wait(12)
    await house.draw("end", **end_payload(water_start, 40.0, 10.0, complete=False))
    await house.wait(10)
    assert hass.states.get("sensor.water_last_draw").state == "other"
    assert num(hass, "sensor.water_other_total") == 40.0
    assert hass.states.get("sensor.water_other_total").attributes["flowing_min"] == 0
    assert hass.states.get("sensor.water_other_average_flow").state == "unavailable"
