# EV Solar Charging Automation — Setup Guide

Tesla Model 3 (Tesla Fleet) + Alfen Eve Single S-line + HomeWizard P1 + solar.

## Contents

| File | Purpose |
|---|---|
| `packages/ev_charging.yaml` | All helpers, template sensors, scripts and automations |
| `dashboard_ev_charging.yaml` | Dashboard view definition |
| `tests/test_ev_charging.py` | Behavioural tests in a real Home Assistant core (see [Tests](#tests)) |

Requires **Home Assistant 2024.10+** (uses the `triggers:` / `conditions:` / `actions:` syntax).

---

## 1. Check your entity IDs

The package assumes these entity IDs. Verify each one in **Developer Tools → States** before installing. If any differ, do a find-and-replace in `packages/ev_charging.yaml`.

| Entity | Role |
|---|---|
| `switch.life_the_universe_and_everything_charge` | Start/stop charging |
| `sensor.life_the_universe_and_everything_battery_level` | Battery % |
| `sensor.life_the_universe_and_everything_odometer` | Learned consumption (disabled by default in Tesla Fleet — enable it) |
| `sensor.life_the_universe_and_everything_charge_energy_added` | Learned consumption: detects charging on the way |
| `number.life_the_universe_and_everything_charge_limit` | Car charge limit |
| `number.life_the_universe_and_everything_charge_current` | Car's amps setting, kept at the charger maximum |
| `button.life_the_universe_and_everything_wake` | Wake the car before a night session |
| `select.ev_charger_solar_charging_mode` | Alfen mode (`Comfort` / `Disable` / `Green`) |
| `sensor.ev_charger_status_code_socket_1_2` | Alfen socket status — used to detect plug-in and load balancing |
| `sensor.ev_charger_current_l1_socket_1` … `l3` | Alfen phase currents — what the car really draws |
| `number.ev_charger_max_station_current` | Alfen maximum current (16 A) |
| `sensor.p1_meter_power` | Grid power, negative = export |
| `sensor.p1_meter_power_phase_1` … `3` | Grid power per phase, for the room under the main fuse |
| `sensor.steca_inverter_ac_power` | Solar production in watts, used by the solar stop gate |

Confirm the select's exact state strings are `Comfort` and `Disable` (case-sensitive).

---

## 2. Remove the old automations

If you already created the solar start/stop automations or the three scripts via the UI, **delete or disable them now**. The package contains updated versions and duplicates would fight each other.

Settings → Automations & Scenes → delete the old "Solar: start…" / "Solar: stop…" automations and the three `EV:` scripts.

---

## 3. Enable packages

Add this to `configuration.yaml` (skip if you already have a `homeassistant:` block — just add the `packages:` line under it):

```yaml
homeassistant:
  packages: !include_dir_named packages
```

---

## 4. Copy the package file

Copy `packages/ev_charging.yaml` into your Home Assistant config directory so the path becomes:

```
/config/configuration.yaml
/config/packages/ev_charging.yaml
```

Create the `packages` folder if it doesn't exist.

---

## 5. Validate and restart

1. **Developer Tools → YAML → Check Configuration**
2. Fix any reported errors
3. **Developer Tools → YAML → Restart** (a full restart is required — new helpers and template entities are not picked up by a quick reload)

---

## 6. Set your initial values

After restart the `input_number` helpers start at their minimum. Set them in **Settings → Devices & Services → Helpers**, or directly on the dashboard once you've added it:

| Helper | Suggested starting value |
|---|---|
| Roundtrip Consumption | `33` — only a fallback until 100 km has been learned, see [Learned consumption](#learned-consumption) |
| Regular Charge Limit | `80` |
| Trip Target SOC | `90` (only used while a trip is armed) |
| Min. Safe SOC | `30` (hard floor, triggers max-power top-up) |
| Safety Charge Min. Duration | `60` |
| Min. Remaining SOC (work) | `25` (commute calculation only) |
| Solar Window Start / End | `09:00` / `17:00` |
| Solar Min. Off Time | `15` |
| Solar Stop Max. Production | `1000 W` (default) |
| Solar Stop Averaging Duration | `20 min` (default) |
| Max Power Charge Rate | `15` |
| Ready Margin | `1` |
| Conditioning Interval | `14` |
| Last 100% Charge Start | Set to the start of your last 100% charge (a realistic recent date), otherwise conditioning shows as due immediately |
| Work Departure Time | Your usual time |
| Workday toggles | Turn on the days you're going to the office this week |
| Last Known SOC | Set once to the car's current battery %, so planning works before the first poll |

These are set once automatically on the first start (by `ev_initialise_settings`) and are yours to change afterwards:

| Helper | Default |
|---|---|
| Hold In Green While Waiting | on |
| Main Fuse Current | `25 A` |
| Roundtrip Distance | `125 km` |
| Consumption Margin | `1 %` |
| Consumption Learning Window | `500 km` |

---

## 7. Add the dashboard

1. Open your EV dashboard → **Edit Dashboard** → 3-dot menu → **Raw configuration editor**
2. **Select all existing content and delete it**
3. Paste the entire contents of `dashboard_ev_charging.yaml`
4. Save

New Home Assistant dashboards are pre-filled with a `sections` view containing an empty "New section" heading. The file replaces that with a classic masonry view. If you'd rather keep the generated section view, paste only the `- title: EV Charging` block (and everything indented under it) as an extra entry under the existing `views:` key.

Alternatively, add each card manually with **Add Card → Manual** and paste one card block at a time — this works with either view type.

---

## 8. Verify the calculation

On the dashboard's "Charging Plan" card, check that `Required SOC` matches your expectation. Quick test:

- Toggle on Mon + Tue + Thu, consumption `26`, min SOC `25`, limit `80`
- If the next departure is Monday: run length `2`, required `77`
- Switch to Mon + Wed + Fri: run length `1`, required `51`
- Switch to Mon + Tue + Wed: run length `3`, uncapped `103`, required `80` (capped)

---

## How it works

### Required SOC

```
required = 100                                     if conditioning is due
         = min(limit, min_soc + run × consumption) otherwise
```

`run` = number of consecutive enabled workdays starting at the next departure day. Weekends always break the run.

`consumption` is `sensor.ev_roundtrip_consumption_effective`: the [learned consumption](#learned-consumption) once 100 km has been learned, otherwise the manual **Roundtrip Consumption**. The quick test in step 8 uses the manual value.

### Conditioning schedule

```
due = (next_departure − last_100%_start) ≥ interval
```

When SOC first rises above 99%, `input_datetime.ev_last_full_charge` stores the time that session **started**, taken from `input_datetime.ev_charge_started`. The finish time isn't used. If no session was stamped in the last 24 h, for example a charge started from the Tesla app, it falls back to the time 100% was reached.

The check uses the **next departure**, not the current time. A conditioning charge is therefore due *for* a departure, and the night session can plan for it in time. The start always comes before the departure it served, so the schedule doesn't drift. With a 7-day interval, a 100% charge for Monday 07:30 leads to the next one being due for the following Monday, whatever time each charge started or finished.

Checking against the current time would only turn conditioning on at the moment it became due. By then the night session is usually too late to reach 100%, so the charge slips to the next workday and the schedule moves one day later every cycle.

The `due_from` attribute on `binary_sensor.ev_conditioning_due` shows the earliest moment a departure qualifies.

### Night charge timing

```
start_time = departure − margin_hours − (deficit / charge_rate) hours
deficit    = max(0, required_soc − current_soc)
```

The night automation re-evaluates every 5 minutes, so plugging in late still works — you just lose margin.

### Session flags

Three booleans define "authorized charging":

| Flag | Set by | Cleared by |
|---|---|---|
| `ev_solar_session` | Solar start automation | Solar stop, charging stops for 2 min, unplug |
| `ev_night_session` | Night start automation | Night end, unplug |
| `ev_max_power_override` | Max Power button | Set Comfort / Stop buttons, target reached, unplug |

Flags are always set **before** the switch is turned on, so the guard can't cancel a legitimate session.

### The guard

Your car starts charging the moment you plug in. The guard stops it — but **only while a timed night session is pending** (i.e. a night charge is scheduled and its start time hasn't arrived). Outside that window, manual charging from the Tesla app is untouched.

### Mode handling

The Alfen has three solar charging modes:

| Alfen mode | What the charger offers the car |
|---|---|
| `Disable` | Solar logic off: full power from the grid (3×16 A, limited only by load balancing) |
| `Comfort` | At least the comfort level (1400 W ≈ 6 A), from the grid if needed, plus solar surplus |
| `Green` | Only solar surplus. Without sun it offers **0 A**, so the car cannot charge |

| Phase | Alfen mode | Who controls it |
|---|---|---|
| Daytime solar | `Comfort` | Solar automations active |
| Night top-up | `Disable` | Set by night start, restored to `Comfort` by night end |
| Manual max power | `Disable` | Set by Max Power button, restored by Set Comfort button |
| Idle, night session pending, outside the solar window | `Green` | `ev_idle_mode_sync` (if **Hold In Green While Waiting** is on) |
| Idle, safety or night start due | `Disable` | `ev_idle_mode_sync` |
| Idle otherwise | `Comfort` | `ev_idle_mode_sync` |

Because the solar stop automation requires `Comfort`, it can never interrupt a night session.

#### Holding the mode while idle

The car starts charging by itself the moment it is plugged in, in whatever mode the charger is in. Before, a plug-in at 18:30 with a night session planned for 01:00 started at 6 A in Comfort, and the guard stopped it a minute later (seen on 20 Nov 2026). `sensor.ev_idle_charger_mode` works out the mode the next session needs, and `ev_idle_mode_sync` holds the charger in it whenever no current flows and no session is running:

- **`Green`** while a night session is pending outside the solar window: the charger offers nothing, so the car just waits. The Tesla app shows it waiting for the charger. Press **Start Max Power** to charge now.
- **`Disable`** when a safety or night start is due: a car plugged in late starts straight at full power and the session adopts it. The guard leaves such a charge alone.
- **`Comfort`** otherwise, so charging from the Tesla app works as before.

It never changes the mode while current flows. Turn off **Hold In Green While Waiting** if the car does not resume after waiting in `Green`; the charger then stays in `Comfort` while waiting, as before.

The solar stop automation also requires production below the configured threshold
on average over the configured number of minutes. It samples the inverter once
per minute; a non-reporting inverter (e.g. offline after sunset) counts as 0 W.
After a restart or reload, missing history is filled with the current inverter
reading, so the average is available immediately. If the inverter has no reading
yet during daylight, filling waits for the first valid reading. The existing grid-import and minimum on-time rules
still apply. Set the two Solar Stop helpers on the dashboard to adjust the gate;
with their YAML `initial` values, they reset to 1000 W and 20 min after a full
Home Assistant restart.

### Handling the sleeping car

Tesla Fleet stops polling while the car sleeps, so `sensor.…_battery_level` reports `unknown`. Three mechanisms keep the logic working:

**Cached SOC.** `ev_record_soc` mirrors every numeric reading into `input_number.ev_last_known_soc` with a timestamp. `sensor.ev_soc_effective` returns the live value when available and the cached one otherwise — its `source` attribute shows which. All planning uses the effective sensor, never the raw Tesla one.

**Alfen-based plug detection.** `binary_sensor.ev_car_plugged_in` is derived from `sensor.ev_charger_status_code_socket_1_2`. The charger is polled locally and always reports, so plug-in detection does not depend on the car being awake. Anything other than `Available`, `Off`, `Booting`, `Check Mains` or `Unknown` counts as plugged in.

**Wake before acting.** Nothing wakes the car automatically. The package operates cache-only: SOC drops only through vampire drain while parked (roughly 1%/day), so the mirrored value stays accurate enough to plan from, and no wakes are paid for.

The car is woken implicitly when the night session issues its first command — that's unavoidable and is how the session gets fresh data anyway. The session's target is enforced by the car's own charge limit, so a slightly stale planning value cannot cause an overcharge.

### Commands sent to a sleeping car get dropped

Tesla's docs are explicit: *"Ensure the vehicle is online before requesting device data or sending commands."* A `switch.turn_on` against a sleeping vehicle wakes it but the command itself is lost, so the first attempt silently does nothing and charging only begins on a later retry.

`script.ev_begin_charging` handles this and is used by all four session starts (solar, night, safety, Max Power). Each passes the charger mode it needs and, optionally, a charge limit. The order avoids a start in the wrong mode followed by a stop:

1. Sets the charger mode via `script.ev_set_charger_mode` and waits until the Alfen reports it, retrying up to 3 times. If it never confirms, nothing starts: a persistent notification is created and the session flags are cleared, so the owning automation retries on its next tick
2. Calls `script.ev_refresh_car_data`, which no-ops if the car is already awake
3. Raises the car's amps setting to what the charger offers (see [Charge current watchdog](#charge-current-watchdog)). After a mode change it first waits 15 s and refreshes the car, because the car's reported maximum follows the charger
4. Sets the charge limit. This comes last, because raising the limit above the SOC makes the car start by itself
5. Sends `switch.turn_on` unless the car is already charging, and verifies the switch actually reports `on`, retrying up to 3 times

This costs nothing extra in practice — the wake was already being incurred by the dropped command, just unreliably and without the wait that makes it succeed.

`script.ev_refresh_car_data` is also wired to the **Refresh Car** dashboard button for manual use.

### The one case where the cache can be wrong

Driving. If you drive 30% away and the car sleeps before the next poll, the cache is stale and the deficit is underestimated.

In practice the car is awake while driving and gets polled during or shortly after the trip, so the mirror is refreshed on arrival. Watch `sensor.ev_soc_age` on the dashboard for the first couple of weeks — if it regularly shows a large value at bedtime, the cache is going stale and it's worth reinstating a scheduled refresh.

The daytime limit reset requires the car to be plugged in, so it won't wake a car parked elsewhere.

---

## Planned trips

For a trip outside normal work hours:

1. Set **Trip Target SOC** to what you need for the trip
2. Set **Trip Departure** to the date and time you leave
3. Turn on **Trip Planned**

Nothing else. The system treats the trip exactly like a workday departure, and your regular charge limit is left alone.

### How it works

`sensor.ev_next_departure` returns the **earliest** of the next workday departure and the trip departure, and exposes a `source` attribute of `work` or `trip`. Every downstream calculation — deficit, start time, session start, guard — is unchanged and simply follows whichever deadline comes first.

When the trip governs, `sensor.ev_required_soc` becomes the trip target rather than the workday commute calculation.

`sensor.ev_daytime_charge_ceiling` is the highest SOC worth reaching today: normally the regular limit, but lifted to the trip target while a trip is armed. Solar charging, the sunrise limit reset, the Max Power button and the session-end restore all use this, so daylight hours can fill toward the trip target without max power being involved.

The trip disarms itself once the departure time passes, so a stale date can't keep driving the schedule.

### Solar and max power mix

This happens automatically, with no extra mode switching:

- **During daylight**, solar charging runs as normal in Comfort mode, filling toward the daytime ceiling. Free energy first.
- **As solar fills the battery**, the deficit shrinks and `sensor.ev_night_charge_start` moves *later*, so the max-power fallback keeps receding.
- **Max power engages only if** the deadline math says solar won't get there in time — `departure − margin − deficit/rate`.

A sunny day before an afternoon trip may never trigger max power at all. A trip departing at 07:00 after a cloudy day will charge at max power overnight. There's at most one mode switch per session, same as before.

### Interaction with conditioning

If a 100% conditioning charge is due, it still takes precedence and the target becomes 100 rather than the trip target. For a trip that's harmless — more range than asked for — and it satisfies the conditioning requirement at max power, as required.

---

## Charging modes

Three independent mechanisms, in priority order.

### 1. Safety floor (highest priority)

Whenever the car is plugged in and `sensor.ev_soc_effective` is below **Min. Safe SOC**, it charges at max power regardless of any planning. It runs for at least **Safety Charge Min. Duration** (default 60 min) even if the floor is reached sooner, to avoid short contactor cycles.

This is deliberately separate from **Min. Remaining SOC (work)**, which is only an input to the workday commute calculation.

The session charges toward the daytime ceiling rather than stopping exactly at the floor, so the minimum duration can actually run.

**When it finishes**, one of three things happens:

| Situation | Outcome |
|---|---|
| Inside the solar window, surplus available, below the ceiling | Switches to Comfort and **keeps charging** — no contactor cycle, solar takes over |
| Inside the solar window, no surplus yet | Stops, switches to Comfort, and **skips the cooldown** so solar can start as soon as surplus appears |
| Outside the solar window | Stops and switches to Comfort. A workday or trip deadline is then handled by the normal timed session |

### 2. Opportunistic solar

Inside the **Solar Window** (default 09:00–17:00), with the charger in Comfort mode and surplus available, the car charges toward the regular charge limit — whether or not any workday or trip is planned. Plug in during the day and it just works.

The window is configurable so you can stop solar charging being attempted at times you don't want it.

#### Plugging in: adopt or stop

The car starts charging by itself the moment it is plugged in, so no automation owns that charge and no session flag is set. Without handling, it would run unmanaged — the solar stop rule only acts on charges flagged as solar sessions.

`ev_unauthorized_charge_guard` handles any charge that no session owns, within one minute and then every 5 minutes:

| Situation | Outcome |
|---|---|
| Solar window, Comfort mode, surplus available, below the ceiling | **Adopted** as a solar session — the normal solar stop rule now governs it |
| Solar window, no surplus | Stopped. No cooldown is stamped, so solar starts as soon as surplus appears |
| Timed night session pending | Stopped (with the Green hold on, the car can't start by itself here at all outside the solar window) |
| A safety or night start is due | Left alone: the charger is held in `Disable` and that session adopts the charge within 5 minutes |
| Outside both | Left alone, so charging started from the Tesla app still works |

Charging is detected with `binary_sensor.ev_charging_active`, derived from the locally polled Alfen status. The Tesla charge switch can lag by a full polling interval after the car starts on its own, which is why it isn't used for this.

### 3. Deadline charging

Workday or trip deadlines trigger a max-power session only when solar won't get there in time. Unchanged.

---

## Charge current watchdog

On 18 Nov 2026 a night session charged at about 5 A per phase for 2.5 hours on a free 16 A charger. The house used only 1.2–1.5 kW per phase, so load balancing wasn't the cause. The charger reported `Charging Normal`, and the car ran at 16 A the moment the amps were raised in the Tesla app. The limit was **the car's own amps setting** (`number.life_the_universe_and_everything_charge_current`). Tesla remembers a lowered setting per location, and the car also reports a maximum (`max` attribute) that follows what the charger offers: 6 A in Comfort without sun.

Load balancing works through the charger's pilot signal, independent of that setting. So the car should always ask for the charger maximum, and the Alfen does the limiting. When a large load disappears, the charger raises its offer again and the car follows.

**Prevention.** `script.ev_begin_charging` raises the car's amps to `sensor.ev_charge_current_target` at every session start: the charger maximum (`number.ev_charger_max_station_current`, 16 A), capped by the car's reported maximum. Home Assistant rejects anything above that maximum, which is why this happens after the charger mode is confirmed.

**Watchdog.** `ev_charge_watchdog` checks every 5 minutes while a session owned by this package is charging. It takes at most one action per 10 minutes, the first that applies:

| Situation | Action |
|---|---|
| Night, safety or Max Power session, but the charger isn't in `Disable` | Switches it back to `Disable` |
| The car asks less than the charger offers, and the Alfen isn't load balancing | Raises the car's amps to the target |
| `binary_sensor.ev_current_shortfall` on (see below), first time this session | Nudges the amps: target − 1 A, then the target again 20 s later |
| Shortfall still on, second time | Pauses charging for 60 s and resumes, once per session |
| Shortfall still on, third time | Only reports |

`binary_sensor.ev_current_shortfall` turns on after **15 minutes** of a night, safety or Max Power session in `Disable` drawing more than 3 A below the charger maximum, while nothing explains it:

- the Alfen does not report `Load Balancing Limited` or `Load Balancing Forced Off`;
- `sensor.ev_current_headroom` (room on the tightest phase: main fuse − P1 phase power ÷ 230 V + the car's own current) is at least the charger maximum;
- the SOC is more than 3 points below the car's charge limit, which excludes the normal taper at the end of a charge.

Every action creates a persistent notification (**EV charge watchdog**), adds a logbook entry and increases `counter.ev_watchdog_corrections`. **Last Correction** and the escalation step for the current session are on the dashboard. Each action costs one Fleet command, and the shortfall steps one data request.

---

## Learned consumption

The workday planning needs the SOC a roundtrip costs. Instead of setting it by hand per season, it is learned from the odometer and the SOC.

`sensor.ev_consumption_history` checks the car every 5 minutes, once odometer and SOC have been stable for a minute. Tesla Fleet writes both as separate updates of one poll, and waiting means both values come from the same poll.

| Since the last check | Treatment |
|---|---|
| The car moved | Driving segment: kilometres and SOC used are added |
| The car moved but the SOC rose, or energy was added | Skipped: charged on the way |
| The car did not move but the SOC changed | Ignored: parked drain or home charging |

Only the most recent **Consumption Learning Window** (default 500 km, about a week of commuting) counts. That way the value follows the seasons by itself, while staying long enough that the 1 % SOC rounding of single drives evens out.

- `sensor.ev_consumption_rate`: learned SOC per 100 km, available from 100 km of data. The `kwh_per_100km` attribute uses the usable capacity from the [battery health package](../ev_battery_health/README.md) when it has one, otherwise its reference capacity, otherwise 60 kWh.
- `sensor.ev_roundtrip_consumption_effective`: rate × **Roundtrip Distance** (125 km) × (1 + **Consumption Margin**). Used by `sensor.ev_required_soc`. Its `source` attribute shows `learned` or `manual`; below 100 km of data it falls back to the manual **Roundtrip Consumption**.

The week of 16–21 Nov 2026 gave 532 km for 132 % SOC: 24.8 %/100 km, so 31 % per roundtrip (the manual value was 33 %), about 14.9 kWh/100 km.

The history can be cleared or seeded from **Developer Tools → Events** with event type `ev_consumption_command`:

```yaml
command: seed   # or: clear
km: 532
soc: 132
```

Seeding adds one segment of that size, for example measured data so the learned value works straight after installing.

---

## Testing without waiting

### Reading traces

Package automations show "cannot be edited because it is not stored in automations.yaml" in the UI. That is expected and harmless — only `automations.yaml` entries are UI-editable. **Traces still work and are the primary debugging tool.**

Settings → Automations → pick one → **Traces**.

- A trace is recorded every time an automation is *triggered*, including when a condition stops it. The failing condition is highlighted.
- **No traces at all means the trigger never fired** — conditions are then irrelevant and the trigger is what needs fixing.

Automations using `time_pattern: /5` (`ev_solar_start`, `ev_solar_stop`, `ev_night_start`) produce a trace every 5 minutes, so there is always something to inspect.

### Test the solar start

1. Check `sensor.p1_power_mean_10min` on the dashboard graph
2. When it sits below −450, the automation should fire within 5 minutes
3. If it doesn't, open Traces and look at which condition failed — most often SOC already at the regular limit, charger not in `Comfort`, or the 10-minute minimum off-time

### Test the night session

The trick is to move the departure time so the calculated start lands in the past.

1. Make sure the car is plugged in and `sensor.ev_charge_deficit` is above 0
2. Note the deficit, e.g. 10% → at 15%/h that's 0.67 h, plus the 1 h margin = 1.67 h
3. Set **Work Departure Time** to roughly 1 hour from now
4. Enable today's (or tomorrow's) workday toggle so `sensor.ev_next_departure` resolves
5. `sensor.ev_night_charge_start` should now show a time in the past
6. Within 5 minutes the session starts: charger switches to `Disable` (confirmed), the car's amps go to 16 A, the charge limit is set, charging begins

Press **Stop Charging** to abort, then restore your real departure time.

### Test the conditioning charge

1. Set `input_datetime.ev_last_full_charge` to ~20 days ago
2. `binary_sensor.ev_conditioning_due` turns on and `sensor.ev_required_soc` jumps to 100
3. Follow the night-session steps above — the session should now set the car's charge limit to **100** rather than the regular limit

Restore the real date afterwards, otherwise the next genuine conditioning charge will be mistimed.

### Running actions directly

Settings → Automations → ⋮ → **Run**. This executes the actions while **skipping triggers and conditions**, which is useful for verifying the action sequence itself (mode switch, limit set, switch on). Be aware it will really start charging.

### Checking a condition by hand

Developer Tools → **Template** and paste any `value_template` from the package to see what it currently evaluates to. Useful for the workday-run and required-SOC logic.

---

## Tesla Fleet API usage and cost

Fleet API is pay-per-use. There is no free tier as such, but **each account receives a $10/month discount**, which covers personal use. Rates from Tesla's developer portal:

| Category | Rate | Per unit |
|---|---|---|
| Wakes | 50 / $1 | $0.020 |
| Data (`vehicle_data` polls) | 500 / $1 | $0.002 |
| Commands | 1,000 / $1 | $0.001 |
| Streaming signals | 150,000 / $1 | $0.0000067 |

Estimated monthly cost for this package at a 30-minute polling interval:

| Source | Volume/month | Cost |
|---|---|---|
| Baseline polling | ~1,440 data | $2.88 |
| Wakes (2–5/day, one per session start against a sleeping car) | 60–150 | $1.20 – $3.00 |
| Refresh-loop data requests | 200–450 | $0.40 – $0.90 |
| Commands (solar, night session, limit sets) | ~300 | $0.30 |
| Amps refresh at session start, watchdog corrections | ~60 data + a few commands | ~$0.12 |
| **Total** | | **$4.90 – $7.20** |

Inside the $10 discount, but without huge margin. **Check your real usage** at [developer.tesla.com/dashboard/usage](https://developer.tesla.com/dashboard/usage) after the first couple of weeks rather than relying on this estimate.

### The billing cliff

Tesla's default billing limit is $0, and applications that exceed their limit or have no payment method configured are **automatically disabled** until the next billing cycle. Staying under $10 means no bill and no risk. Going over without a payment method on file silently kills API access and therefore every automation here.

### Wakes are the expensive category

A wake costs 10× a data request and 20× a command. Each session start wakes the car if it is asleep, via `script.ev_begin_charging`. This is not additional cost — a command sent to a sleeping car already triggered a wake, it just got dropped and had to be retried. Making the wake explicit means it succeeds first time.

Once a session is running the car stays awake, so closely-spaced restarts skip the wake entirely.

### Levers if usage runs high

| Lever | Saving | Trade-off |
|---|---|---|
| `Solar Min. Off Time` 15 → 30 min | Fewer sessions, fewer wakes | Misses short surplus windows |
| Polling interval 30 → 60 min | ~$1.44 | Staler data — harmless, the package is cache-only |
| Raise the −450 W start threshold | Fewer, longer sessions | Less solar captured |
| Fleet Telemetry | Removes the baseline *and* most wakes | Setup effort; vehicle must support it |

Lowering the polling interval is the easiest win, since nothing in this package depends on frequent polling.

### Rate limits

Per device, per account: 60 realtime data requests/min, 3 wakes/min, 30 commands/min. The refresh loop runs 3 data requests/min and issues at most one wake per invocation, so there is ample headroom.

### Biggest available saving

Migrating to **Fleet Telemetry** streaming eliminates polling entirely — the car pushes signals when values change, and its online state becomes visible without a wake. Tesla's published case studies show 94–97% cost reductions. Check whether your Tesla integration and vehicle support it.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| `Setup of package 'ev_charging' failed: integration 'script' has duplicate key 'alias'` | `/config/scripts.yaml` contains a flat script (starts with `alias:`) instead of a mapping of script IDs. Empty the file with `{}` — the package defines all three scripts |
| `...integration 'script' has duplicate key 'ev_start_max_power'` | The old UI-created script still exists in `scripts.yaml`. Delete that entry |
| `...integration 'automation' cannot be merged` | `automations.yaml` must be a **list** — every entry starts with `- id:`. A flat block pasted at the top level breaks it |
| `sensor.ev_next_departure` is `unavailable` | No workday toggles are on |
| `sensor.ev_night_charge_start` is `unavailable` | Deficit is 0 — car already has enough charge |
| `sensor.ev_charge_deficit` is `unavailable` | No SOC has ever been cached. Wake the car once, or set `input_number.ev_last_known_soc` manually |
| `binary_sensor.ev_car_plugged_in` is wrong | Check what `sensor.ev_charger_status_code_socket_1_2` reports and add that value to the exclusion list in the template |
| `sensor.ev_soc_age` shows `999` | SOC has never been mirrored — same fix as above |
| Charging stops right after plugging in | Expected, if a night session is pending and the Green hold is off. Press **Start Max Power** to override |
| Car shows "waiting for charger" after plugging in | Expected while a night session is pending: the charger is held in `Green`. Press **Start Max Power** to charge now, or turn off **Hold In Green While Waiting** |
| "EV charger mode not confirmed" notification | The Alfen did not switch within 3 × 30 s. Check the Alfen integration; the session retries every 5 minutes |
| "EV charge watchdog" notification | The watchdog corrected a session; the message says what it found. Repeated corrections every night point at the car or the charger, not the automation |
| `sensor.ev_consumption_rate` stays `unavailable` | Less than 100 km learned. Check that the Tesla odometer entity is enabled, or seed the history (see [Learned consumption](#learned-consumption)) |
| Conditioning always shows due | `input_datetime.ev_last_full_charge` is unset — set it manually once |
| Night charge never starts | Check cable connected, deficit > 0, and that `ev_max_power_override` is off |
| Automations don't appear in the UI editor | Expected — YAML package automations are read-only in the UI. Edit the file and reload |

### Expected shape of the include files

`scripts.yaml` — mapping of IDs:

```yaml
some_script_id:
  alias: My Script
  sequence:
    - ...
```

`automations.yaml` — list:

```yaml
- id: "1234567890"
  alias: My Automation
  triggers:
    - ...
```

If either file holds only the EV entries we superseded, replace its contents with `{}` (scripts) or `[]` (automations).

### Reloading after edits

Most changes need only a targeted reload:

- Template sensors: **Developer Tools → YAML → Template entities**
- Automations: **Developer Tools → YAML → Automations**
- Scripts: **Developer Tools → YAML → Scripts**

Changes to `input_boolean` / `input_number` / `input_datetime` definitions require a full restart.

---

## Seasonal adjustment

Not needed any more: the [learned consumption](#learned-consumption) follows the season by itself. **Roundtrip Consumption** is only the fallback until 100 km has been learned. Change **Roundtrip Distance** if your commute changes.

---

## Tests

The tests load the package into a real Home Assistant core and simulate the Tesla and the Alfen. They use the shared Home Assistant virtual environment (`tools\setup.cmd home-assistant` creates it):

```powershell
cd projects\home-assistant\ev_charging_automation
..\..\..\.venvs\home-assistant\Scripts\python.exe -m pytest -q
```
