"""Behavioural tests for packages/heatpump_monitor.yaml.

The package runs in a real Home Assistant core instance. The P1P2MQTT bridge
entities are plain states; the statistics sensors the learner reads are set
directly instead of being computed.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml_dict
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

PACKAGE = Path(__file__).resolve().parents[1] / "packages" / "heatpump_monitor.yaml"
FS = "sensor.bridge0_fieldsettings_"
LOW_AMB = f"{FS}1_00_a3113_lwt_heating_main_wd_curve_low_amb"
HIGH_AMB = f"{FS}1_01_a3113_lwt_heating_main_wd_curve_high_amb"
LWT_LOW = f"{FS}1_02_a3113_lwt_heating_main_wd_curve_low_amb_lwt"
LWT_HIGH = f"{FS}1_03_a3113_lwt_heating_main_wd_curve_high_amb_lwt"
OUT_12H = "sensor.hp_outside_temperature_mean_12h"
ROOM = "sensor.bridge0_sensors_temperature_room"
OFFSET = "sensor.bridge0_lwt_deviation_heating"
LEARN = "sensor.hp_curve_learning"
SUGGEST = "sensor.hp_curve_suggestion"


async def pump(hass: HomeAssistant) -> None:
    for _ in range(50):
        await asyncio.sleep(0)
    await hass.async_block_till_done()


@pytest.fixture
async def hass_hp(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> HomeAssistant:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-11-23 20:01:00+00:00")
    for entity_id, state in {
        LOW_AMB: -10, HIGH_AMB: 10, LWT_LOW: 33, LWT_HIGH: 26, f"{FS}9_09_delta_t": 5,
        f"{FS}9_00_a31122_temp_heating_main_max": 40, f"{FS}9_01_a31121_temp_heating_main_min": 25,
        "switch.bridge0_mode_altherma_on": "on", "select.bridge0_mode_program_wd_abs": "WD",
        "select.bridge0_mode_heating_cooling_auto": "Heating", OFFSET: 0,
        "sensor.bridge0_room_room_heating_setpoint": 22, "sensor.bridge0_lwt_lwt_setpoint": 28.5,
        ROOM: 20.5, OUT_12H: 3.3,
    }.items():
        hass.states.async_set(entity_id, str(state))
    config = await hass.async_add_executor_job(load_yaml_dict, str(PACKAGE))
    for domain in ("input_boolean", "input_number", "script"):
        assert await async_setup_component(hass, domain, {domain: config[domain]})
    for entity_id, value in {"input_number.hp_room_target": 21, "input_number.hp_curve_min_hours": 12}.items():
        await hass.services.async_call("input_number", "set_value", {"entity_id": entity_id, "value": value}, blocking=True)
    assert await async_setup_component(hass, "template", {"template": config["template"]})
    await hass.async_block_till_done()
    return hass


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    target = dt_util.utcnow() + timedelta(minutes=10)
    async_fire_time_changed(hass, target)
    freezer.move_to(target)
    await pump(hass)


async def seed(hass: HomeAssistant, bins: list[list[float]]) -> None:
    """Restore the learner with prepared bins, as after a restart."""
    hass.states.async_set(LEARN, "1", {"bins": bins, "curve": "-10/10/33/26", "since": "2026-11-20T00:00:00+01:00",
                                         "previous_bins": [], "previous_curve": "", "last_event": ""})
    await pump(hass)


async def test_learner_bins_room_temperature_and_pauses_on_offset(hass_hp, freezer):
    await tick(hass_hp, freezer)
    assert hass_hp.states.get(LEARN).attributes["bins"] == [[2, 1, 3.3, 20.5, 28.5]]

    hass_hp.states.async_set(ROOM, "20.7")
    await tick(hass_hp, freezer)
    assert hass_hp.states.get(LEARN).attributes["bins"] == [[2, 2, 3.3, 20.6, 28.5]]

    hass_hp.states.async_set(OUT_12H, "-0.4")
    await tick(hass_hp, freezer)
    assert [b[0] for b in hass_hp.states.get(LEARN).attributes["bins"]] == [-2, 2]

    hass_hp.states.async_set(OFFSET, "2")
    await tick(hass_hp, freezer)
    state = hass_hp.states.get(LEARN)
    assert state.attributes["last_event"] == "paused: LWT offset active"
    assert sum(b[1] for b in state.attributes["bins"]) == 3
    assert state.state == "0.5"


async def test_mature_bin_still_follows_small_changes(hass_hp, freezer):
    # 300 samples (50 h): each new sample moves the mean by 1/300 of the difference.
    await seed(hass_hp, [[2, 300, 3.3, 20.5, 28.5]])
    hass_hp.states.async_set(ROOM, "20.8")
    for _ in range(3):
        await tick(hass_hp, freezer)
    room = hass_hp.states.get(LEARN).attributes["bins"][0][3]
    assert room == pytest.approx(20.503, abs=1e-4)


async def test_curve_change_starts_new_learning_and_keeps_previous(hass_hp, freezer):
    await tick(hass_hp, freezer)
    hass_hp.states.async_set(LWT_LOW, "34")
    await tick(hass_hp, freezer)
    state = hass_hp.states.get(LEARN)
    assert state.attributes["previous_curve"] == "-10/10/33/26"
    assert state.attributes["previous_bins"] == [[2, 1, 3.3, 20.5, 28.5]]
    assert state.attributes["curve"] == "-10/10/34/26"
    # The same tick already records the first sample of the new curve.
    assert state.attributes["bins"] == [[2, 1, 3.3, 20.5, 28.5]]

    await hass_hp.services.async_call("script", "hp_curve_reset", blocking=True)
    await pump(hass_hp)
    state = hass_hp.states.get(LEARN)
    assert state.attributes["bins"] == []
    assert state.attributes["last_event"] == "reset by user"


async def test_cold_bin_too_cold_suggests_steeper_curve(hass_hp, freezer):
    # 12 h each. At 0 Â°C the room is 1 K below target, at 8 Â°C it is on target.
    await seed(hass_hp, [[0, 72, 0.0, 20.0, 29.5], [8, 72, 8.0, 21.0, 26.7]])
    state = hass_hp.states.get(SUGGEST)
    assert state.state == "Steeper curve"
    # The fitted correction is +3 K at -10 Â°C, limited to +2 K per step.
    assert state.attributes["suggested_lwt_at_low_ambient"] == 35
    assert state.attributes["suggested_lwt_at_high_ambient"] == 26
    assert state.attributes["rows"][0]["correction"] == 1.4


async def test_single_warm_bin_shifts_curve_down(hass_hp, freezer):
    await seed(hass_hp, [[4, 72, 4.0, 21.6, 28.1]])
    state = hass_hp.states.get(SUGGEST)
    assert state.state == "Lower curve"
    assert (state.attributes["change_at_low_ambient"], state.attributes["change_at_high_ambient"]) == (-1, -1)


async def test_bins_below_min_hours_only_collect(hass_hp, freezer):
    await seed(hass_hp, [[4, 30, 4.0, 19.0, 28.1]])
    state = hass_hp.states.get(SUGGEST)
    assert state.state == "Collecting data"
    assert state.attributes["rows"][0]["correction"] is None

    await hass_hp.services.async_call(
        "input_number", "set_value", {"entity_id": "input_number.hp_curve_min_hours", "value": 4}, blocking=True)
    await pump(hass_hp)
    assert hass_hp.states.get(SUGGEST).state == "Raise curve"


async def test_control_off_alert_ignores_bridge_outage(hass_hp, freezer):
    notes = async_mock_service(hass_hp, "persistent_notification", "create")
    for switch in ("control_function", "counter_request_function"):
        hass_hp.states.async_set(f"switch.bridge0_bridge_{switch}", "on")
    config = await hass_hp.async_add_executor_job(load_yaml_dict, str(PACKAGE))
    assert await async_setup_component(hass_hp, "automation", {"automation": config["automation"]})
    await pump(hass_hp)
    assert hass_hp.states.get("automation.heat_pump_monitor_alerts").state == "on"
    await hass_hp.services.async_call("input_boolean", "turn_on", {"entity_id": "input_boolean.hp_alerts_enabled"}, blocking=True)

    hass_hp.states.async_set("switch.bridge0_bridge_control_function", "unavailable")
    await pump(hass_hp)
    await tick(hass_hp, freezer)
    assert notes == []

    hass_hp.states.async_set("switch.bridge0_bridge_control_function", "off")
    await pump(hass_hp)
    await tick(hass_hp, freezer)
    assert [n.data["notification_id"] for n in notes] == ["hp_bridge_control_off"]
