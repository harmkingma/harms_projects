# EV Battery Health Monitor — Setup Guide

> Archive environment: this copy uses the shared `.venvs\home-assistant`.
> `install_requirements.bat dev` and `activate.bat` forward to that environment.
> The [archive setup instructions](../../../README.md) supersede historical local
> `.venv` instructions below; source files remain unchanged in their original location.

Estimates the usable capacity and state of health (SOH) of the Tesla Model 3
Premium RWD 60 kWh LFP pack over time, from data Tesla Fleet already
provides. It is **read-only**: it never commands the car or the charger and is
independent of the [EV charging package](../ev_charging_automation/README.md),
which it does not modify. Both run side by side.

## Contents

| File | Purpose |
|---|---|
| `packages/ev_battery_health.yaml` | Settings, measurement state machine, estimates, scripts |
| `dashboard_ev_battery_health.yaml` | Separate dashboard |
| `tests/` | Behavioural tests running the package in a real Home Assistant core |
| `requirements.txt`, `requirements-dev.txt`, `overrides-dev.txt` | Test environment (Home Assistant itself needs nothing) |
| `install_requirements.bat`, `activate.bat` | Create and enter the test environment |

Requires **Home Assistant 2024.10+**.

---

## 1. Enable and check the Tesla entities

**Odometer** is disabled by default in Tesla Fleet: Settings → Devices & services →
Tesla Fleet → your car → enable it. Then check these IDs in **Developer Tools → States**.
If any differ, find-and-replace them in `packages/ev_battery_health.yaml`.

| Entity | Role |
|---|---|
| `sensor.life_the_universe_and_everything_battery_level` | SOC |
| `sensor.life_the_universe_and_everything_charge_energy_added` | Energy added per charge session |
| `sensor.life_the_universe_and_everything_charging` | Detects the start of charging |
| `binary_sensor.life_the_universe_and_everything_charge_cable` | Detects unplug |
| `sensor.life_the_universe_and_everything_odometer` | Detects driving; logged per sample |
| `sensor.life_the_universe_and_everything_outside_temperature` | Cold-session filter |
| `sensor.life_the_universe_and_everything_battery_range` | Rated range cross-check |

Units are converted if your system reports miles or °F.

## 2. Install the package

Packages are already enabled for the EV charging package. Copy the file so the path becomes:

```
/config/packages/ev_battery_health.yaml
```

Then **Developer Tools → YAML → Check Configuration**, and **Restart** (a full
restart; new helpers are not picked up by a reload).

On first start an automation initialises the settings once:

| Setting | Default | Meaning |
|---|---|---|
| Reference Usable Capacity | `60.0 kWh` | Capacity of the new pack; SOH = estimate / this |
| Min. SOC Gain | `30 %` | Shorter sessions are rejected (integer-SOC rounding) |
| Min. Outside Temperature | `5 °C` | Colder sessions are rejected |
| Max. Days Since 100% | `14 d` | Sessions starting longer after the last 100% charge are rejected (LFP SOC drift) |

Later edits on the dashboard are kept across restarts.

## 3. Add the dashboard

1. **Settings → Dashboards → Add dashboard → New dashboard from scratch**, name it e.g. *EV Battery Health*
2. Open it → **Edit Dashboard** → 3-dot menu → **Raw configuration editor**
3. Select all, delete, paste the entire `dashboard_ev_battery_health.yaml`, save

---

## How it works

```
usable capacity (kWh) = energy added (kWh) / (SOC gained / 100)
SOH (%)               = median capacity of the last 10 accepted sessions / reference × 100
```

**Snapshots, not start/end values.** Tesla Fleet polls about every 10 minutes
while the car is awake. During a plug-in session each poll's SOC and energy
counter are compared with the previous poll and the differences are summed.
Consequently, the result does not depend on catching the exact start or end of
charging, and a poll that arrives late only shifts the window.

**Solar pauses.** When charging resumes, the car may start a new charge session
and its energy counter restarts at zero. A falling counter is treated as a
reset: that single interval is skipped, the rest of the session still counts.

**A session ends** when the cable is unplugged, the odometer moves, SOC drops
more than 2 points between polls (a missed unplug), or after 7 days. It is then
checked and recorded, accepted or rejected, with the reason.

**Acceptance rules** (all must pass): SOC gain ≥ the minimum; minimum outside
temperature during the session ≥ the limit; days since the last 100% charge at
session start ≤ the limit (unknown counts as pass); capacity within 60–115% of
the reference (catches glitches).

The last 100% charge is recorded by this package whenever SOC reaches 100%. Until
it has seen one, it reads `input_datetime.ev_last_full_charge` from the
charging package as a read-only fallback.

### Entities

| Entity | Meaning |
|---|---|
| `sensor.ev_battery_usable_capacity` | Median of the last 10 accepted sessions (needs ≥ 3). Attributes: `spread_kwh` (median absolute deviation), `window`, `last_sample` |
| `sensor.ev_battery_soh` | Capacity vs reference, % |
| `sensor.ev_battery_capacity_change` | Change vs your own baseline, % |
| `sensor.ev_battery_capacity_last_session` | Capacity from the latest accepted session (the scatter behind the median) |
| `sensor.ev_battery_range_at_100` | Rated range scaled to 100%, only taken at ≥ 60% SOC |
| `sensor.ev_battery_health_measurement` | `idle` / `measuring`, with the running session in its attributes |
| `sensor.ev_battery_health_history` | Number of accepted samples. Attributes: last 50 `samples`, last 15 `recent_sessions` (incl. rejected, with reason), `baseline_kwh`, `baseline_date` |

The numeric sensors have long-term statistics, which Home Assistant keeps
indefinitely; the dashboard graphs use those.

### Two ways to read the trend

- **SOH vs reference** depends on the 60.0 kWh reference being the pack's true
  usable capacity when new. EV-database lists 60.0 kWh usable (64.0 kWh
  nominal) for the Model 3 RWD LFP pack, both marked as estimates. If the 60 kWh
  you have is a gross figure, the true usable value is lower and the SOH shown
  will read low; change the reference on the dashboard. The history is
  unaffected because samples are stored in kWh.
- **Change since baseline** compares against the median of your first 5
  accepted sessions, so it needs no reference at all. The car was already
  ~8 months / ~15 000 km old at install, so this is change since then, not since new.

The rated range at 100% is a second, BMS-derived indicator. It is not
independent, but if it and the capacity estimate trend the same way, that is
supporting evidence.

### Interpreting the numbers

- **Expect scatter.** SOC is an integer: on a 30-point session one point is
  ~3% capacity error, on 50 points ~2%. The BMS SOC itself is an estimate. Look
  at the median and the trend over months, never at one session.
- **First results** need 3 accepted sessions for the capacity and SOH, and 5
  for the baseline. Until then the dashboard shows "Collecting data — n of 3"
  instead of the SOH gauge, and the other estimates read *unknown*. A day of
  solar charging counts as one session as long as the car stays plugged in, so
  it can still reach the minimum gain.
- **LFP and 100% charges.** The BMS recalibrates at 100%; between full
  charges its SOC drifts. Keeping your regular 100% conditioning charges improves
  both the battery management and these estimates. `dsf` in the history shows
  the days since 100% for each session if you want to check the effect.
- **Winter** affects capacity readings (and consumption) without being
  degradation; cold sessions are excluded by default. Lower the limit if winter
  leaves too few sessions, and compare.
- **Energy source.** The estimate uses the car's own reported energy added,
  not the Alfen's or P1's meter, which also include charging losses. DC fast
  charging sessions count as well.

### Commands

| Script | Effect |
|---|---|
| `script.ev_bh_discard_measurement` | Ends the running session as rejected ("discarded manually"). If the car is still charging, a new measurement starts at the next poll. |
| `script.ev_bh_clear_history` | Deletes all samples, recent sessions and the baseline. Long-term statistics are not affected. |

Do not rename `sensor.ev_battery_health_measurement` or
`sensor.ev_battery_health_history`: their templates read their own previous
values by these IDs. They are restored after a restart.

---

## Tests (optional, for changing the package)

The tests load the package into Home Assistant 2026.2.3 (the newest release that
still runs on Python 3.13) and simulate Tesla polls: full sessions, solar pauses
with counter resets, every rejection rule, LFP calibration age, driving/SOC-drop
end detection, staggered entity updates, commands, restart restore, recorder
attribute size limit, and the dashboard's markdown templates.

```bat
install_requirements.bat dev
call activate.bat
python -m pytest
```

`install_requirements.bat` creates `.venv` with Python 3.13 (falling back to
`py -3`, then `python`) and is safe to re-run. The `dev` extra is installed with
uv using `overrides-dev.txt`, because Home Assistant pins an `lru-dict` that has
no Windows wheel for Python 3.13. `activate.bat` works from any directory and
must be `call`ed so the activation stays in your shell.

Home Assistant core does not support Windows; `conftest.py` stubs the two
POSIX-only modules it imports at startup (`fcntl`, `resource`) and allows the
local socket pair the Windows event loop needs. Neither affects the package
logic under test.

This solution runs inside Home Assistant, so it is not registered with
`deploy.py`, which builds standalone Python tools.

## Sources

- [Home Assistant — Tesla Fleet](https://www.home-assistant.io/integrations/tesla_fleet/) (entities, polling)
- [Tesla Fleet sensor source](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tesla_fleet/sensor.py) (energy-counter reset handling, units)
- [Home Assistant — Template](https://www.home-assistant.io/integrations/template/) (trigger-based template sensors)
- [EV-database — Tesla Model 3 RWD](https://ev-database.org/car/3403/Tesla-Model-3-RWD) (60.0 kWh usable / 64.0 kWh nominal LFP, estimated)
- [TeslaMate FAQ](https://docs.teslamate.org/docs/faq/) (deriving consumption from charging data)
