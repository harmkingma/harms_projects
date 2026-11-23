# Heat Pump Monitor (Daikin Altherma R hybrid via P1P2MQTT)

This is a read-only monitor and dashboard for the Daikin Altherma R hybrid. It gets its data from the
[P1P2MQTT bridge](https://github.com/Arnold-n/P1P2MQTT), which is connected to the P1/P2 thermostat bus.
It shows:

- room and outside temperatures
- water and refrigerant temperatures
- heat output and COP
- the weather-dependent (WD) curve

It also learns how warm the room gets at each outside temperature and suggests curve changes.
Nothing here writes to the Daikin. The controls on the dashboard are for manual use and for future automations.

| File | Purpose |
|---|---|
| [packages/heatpump_monitor.yaml](packages/heatpump_monitor.yaml) | Package: derived sensors, curve learning, energy/COP, alerts |
| [dashboard_heatpump.yaml](dashboard_heatpump.yaml) | Dashboard with 5 views (raw config, built-in cards only) |
| [entity_inventory.md](entity_inventory.md) | All 457 entities the bridge publishes, with snapshot values and notes |
| [tests/test_heatpump_monitor.py](tests/test_heatpump_monitor.py) | Behaviour tests for the curve learner and suggestion |

## Bridge settings

The bridge is called `bridge0`. Set it up in HA: **Settings → Devices & services → MQTT → Devices**.

| Device | Setting | Value | Why |
|---|---|---|---|
| bridge0_Bridge | Control_Function | **on** | Makes the bridge an auxiliary controller. Needed for the field settings (the curve), the LWT offset, Altherma on/off and the mode selects. New entities take 10–20 min to appear. |
| bridge0_Bridge | Counter_Request_Function | **on** | Requests the Daikin kWh, hour and start counters every minute. Needed for COP from the counters and starts per day. |
| bridge0_Setup | HA_Setup | off, once the dashboard works | Recommended by the bridge docs after setup. |
| bridge0_Bridge | EEPROM_ESP_Save_Changes | press after changing HA_Setup | Makes the bridge settings permanent. |

Too many bus errors make the bridge switch Control_Function and Counter_Request_Function off by itself
(Error_Budget). The package then raises a persistent notification.

## Install

1. Copy `packages/heatpump_monitor.yaml` to `/config/packages/`.
   This assumes `homeassistant: packages: !include_dir_named packages` is already in place.
2. Restart Home Assistant. The *initialise settings* automation sets room target 21 °C and 12 h per bin, once.
3. Create a dashboard and paste [dashboard_heatpump.yaml](dashboard_heatpump.yaml) into the raw configuration editor.

## Your system (read 23 Nov 2026)

| Setting | Value | Meaning |
|---|---|---|
| Control | RT, WD mode | The room thermostat is master. The LWT follows the WD curve. |
| [1-00] / [1-02] | −10 °C → 33 °C | LWT at the cold end of the curve |
| [1-01] / [1-03] | 10 °C → 26 °C | LWT at the mild end of the curve. Flat beyond both ends. |
| [1-0A] | 1 = 12 h | Outside temperature averaging used by the curve |
| [9-01] / [9-00] | 25 … 40 °C | Allowed LWT range of the main zone; suggestions stay inside it |
| RT modulation | off | The room thermostat does not bend the LWT. This is good for curve tuning. |
| [5-00] / [5-01] | on, −6 °C | Below −6 °C outside, only the gas boiler heats |
| [7-04] / [7-03] | ecological, PE factor 2.5 | Gas vs heat pump is chosen on primary energy. The price settings are not used. |
| [9-09] | 5 K | Target delta T |
| Room thermostat setpoint | 22 °C | Set above the target so it never stops the heat pump |
| Lifetime | 18 755 kWh heat / 5 072 kWh electricity | Lifetime COP 3.7, 5 114 compressor starts |

Check: at 2 °C outside the curve gives 26 + 7 × 8/20 = 28.8 °C, and the Daikin LWT setpoint was 28.7 °C.

## Controls for later automations

| What | Entity | Notes |
|---|---|---|
| LWT offset (shift of the WD curve) | `climate.bridge0_lwt_deviation_heating` | `climate.set_temperature`, −10 … +10 K in 1 K steps. Positive = warmer water (extra floor heating), negative = low-temperature / low-power mode. Read back: `sensor.bridge0_lwt_deviation_heating`. |
| Space heating on/off | `switch.bridge0_mode_altherma_on` | Same as the power button on the thermostat |
| Room thermostat setpoint | `climate.bridge0_room_room_heating` | RT mode. Also has hvac mode off/heat. |
| WD vs absolute LWT | `select.bridge0_mode_program_wd_abs` | `Abs`, `WD`, `Abs+prog`, `WD+prog` |
| Quiet mode / level | `select.bridge0_quiet_quiet_mode`, `select.bridge0_quiet_quiet_level` | Level 1–3 limits fan and compressor (power limitation) |

Every write uses one unit of `number.bridge0_bridge_write_budget`. The budget refills by 1 every
`Write_Budget_Period` minutes (15). The curve itself (field settings) can only be changed on the Daikin interface.

## Curve tuning

The goal is a constant room temperature at any outside temperature, controlled by the curve alone.

**Learning** (`sensor.hp_curve_learning`)
- Takes a sample every 10 minutes and stores the room temperature in a 2 K bin of the 12 h outside mean.
  This is the same input the Daikin curve uses.
- Samples are only taken while space heating is on, in WD mode, with LWT offset 0 and the room below the
  thermostat setpoint − 0.3 K.
- Each bin is a running mean that forgets old data after about 3 days of samples.
- When you change [1-00]…[1-03], learning restarts by itself. The old bins stay visible as "Previous curve",
  so you can compare before and after.
- **Reset learning** on the dashboard starts over by hand.

**Suggestion** (`sensor.hp_curve_suggestion`)
- For each bin with at least *Min. hours per bin* of data, the room deviation from the target is converted into
  an LWT change.
- For a floor-heated room in steady state, ΔT_room = ΔT_water × (T_room − T_out) / (T_water − T_out),
  with T_water ≈ curve LWT − [9-09]/2. Example: at 2 °C outside, 1 K more room temperature needs about 1.4 K more LWT.
- The changes of all bins are fitted with a line and evaluated at [1-00] and [1-01]. A tilt is only suggested
  with data spread over at least 4 K of outside temperature; otherwise the whole curve shifts.
- The result is limited to ±2 K per step, kept within [9-01]…[9-00] and rounded to whole degrees. The state is
  *Curve OK*, *Raise/Lower curve* or *Steeper/Flatter curve*.

**How to use it**
- Change one step at a time on the Daikin interface, then wait 2–3 days. Floor heating is slow.
- The cold end ([1-02]) can only be tuned on cold days, so expect the curve to settle over a season.
- Sun, wind, cooking, guests and the air conditioners also heat or cool the room. Several days per bin
  average these out.

## Other sensors

| Entity | What |
|---|---|
| `sensor.hp_curve_lwt` | Curve LWT at the 12 h outside mean, with the curve settings as attributes |
| `sensor.hp_room_deviation`, `sensor.hp_indoor_outdoor_difference` | Room − target, room − outside |
| `sensor.hp_outside_temperature_mean_12h` / `_24h`, `sensor.hp_room_temperature_mean_24h` | Time-weighted means |
| `sensor.hp_heat_output_heat_pump` / `_gas_boiler` / `_total` | Heat output (W). Gas boiler noise is suppressed while it is off. |
| `sensor.hp_electrical_power_estimate` | Bridge estimate: inverter current × 230 V, not metered |
| `sensor.hp_cop_now` | Real-time COP while the compressor runs |
| `sensor.hp_cop_today` / `_yesterday` / `_this_month` / `_lifetime` | COP from the Daikin counters (whole kWh) |
| `sensor.hp_cop_today_estimate` | Same-day COP from the live estimates |
| `sensor.hp_heat_loss_coefficient` | Heat delivered per K of indoor–outdoor difference over 24 h (W/K) |
| `sensor.hp_compressor_starts_daily`, `sensor.hp_average_compressor_run_today`, `sensor.hp_defrosts_today` | Cycling indicators |

**Alerts** (persistent notifications; switch them off with *Monitor alerts*)
- bridge offline for 15 minutes
- Daikin error code
- Control_Function or Counter_Request_Function switched off

## Tests

From this folder:

```powershell
..\..\..\.venvs\home-assistant\Scripts\python.exe -m pytest -q
```
