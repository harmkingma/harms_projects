# Home Battery & Energy Contract Analysis

Answers three questions from your own meter data:

1. **Is a home battery worth it?** Savings, payback and cycles for the battery you enter (default
   5 kWh usable, 2.4 kW, € 3000), plus a size sweep (2.5–15 kWh).
2. **Fixed or dynamic contract from May 2027?** For electricity and gas, with and without a battery.
3. **What changes in 2029?** That is when time-dependent network tariffs for households are planned.

There are two parts. They use the same battery rules and the same settings:

| Part | What it does |
|---|---|
| `packages/home_battery.yaml` | Live, every minute. It runs four virtual batteries on the real P1 import/export and keeps running € totals for 8 scenarios plus gas. It stores the EnergyZero price forecast and sums your usage per consumer. |
| `addon/energy_analyzer/` | Every night. It replays the **last 12 months** of hourly P1 and gas statistics against the real historical EnergyZero prices. This gives a full-year answer straight away, including the summer that live tracking until May 2027 would miss. |
| `dashboard_home_battery.yaml` | Four views: **Energy** (flows and breakdown), **Prices** (forecast), **Price history** (rolling 12 months, dynamic vs fixed), **Battery & contract** (verdict, tables, settings). |

The add-on also writes the last 12 months of hourly all-in prices into HA's long-term statistics every
night, so the **Price history** graphs move along by themselves:
`energy_analyzer:electricity_dynamic`, `energy_analyzer:electricity_fixed`, `energy_analyzer:gas_dynamic`
and `energy_analyzer:gas_fixed`. The fixed lines are your current fixed settings. The monthly table
puts the plain average dynamic price next to the average **weighted by your own use**: your import per
hour times that hour's price. The difference shows whether your timing helps or hurts on a dynamic contract.

### Months without meter data (estimate)

Until there is a full year of meter history, the add-on estimates the missing hours from the **real
weather of those hours**. The weather comes from the Open-Meteo historical archive: temperature and
irradiance on your panels (`pv_kwp`, `pv_tilt`, `pv_azimuth`). Your HA location, rounded to 0.01°, is
sent to Open-Meteo.

It fits these on your measured days:

- **Solar:** kWh per kWh/m² of sunlight on the panels, from the Steca energy statistic with the most history.
- **Consumption:** base load plus a heating part (per degree-day below 16 °C) plus a cooling part (per
  degree above 24 °C daily maximum), each with its own spread over the day.
- **Gas:** a hot-water base plus a heating part per degree-day.

These are applied to the missing hours, netted to import/export, and replayed against that month's real
prices. Every month shows *measured* or *estimated*. The verdict shows the fit error. As real data comes
in, estimates are replaced; after 12 months there are none left. Your EV's solar charging is part of
the base pattern, so estimated summer export is probably a bit too high. Set `estimate_missing: false`
to switch the estimate off.

### When does dynamic pay off?

Dynamic follows the market, so it wins on average when fixed offers carry a risk premium, and it loses
during a price spike. It works best when your use is flexible:

- an EV or battery charged in the cheap hours;
- a heat pump or boiler that can shift;
- no big evening peak.

The year simulation uses the hours you actually used energy, at the prices of that past period. It does
not shift loads, and it compares past market prices with a fixed price offered *now*. With less than a
year of meter history the missing months are absent; the verdict warns about this.

## Scenarios

All totals leave out the network costs and the energy tax reduction, because they are the same in every
scenario. Costs per year include the monthly supply fees.

| Tariff | Import | Export |
|---|---|---|
| Fixed 2027 | your fixed all-in price | feed-in compensation − feed-in costs (net metering ends 1 Jan 2027) |
| Dynamic 2027 | market (incl. VAT) + markup + energy tax | market (excl. VAT unless switched on) − feed-in fee |
| Fixed / Dynamic 2029 | as above + **Grid Rate × hourly weight** | as above (no network tariff on export) |

Each tariff has a "no battery" and a "battery" case. The battery runs one price-aware strategy on that
tariff's own import price:

- It always stores surplus.
- It covers import only in the most expensive known quarter-hours. The number of quarter-hours is how
  long the stored energy plus the expected solar would last at your typical load.
- It charges from the grid in the cheapest quarter-hours when the later value × round-trip efficiency
  beats the price by at least *Min. Spread*. It leaves room for expected solar, using yesterday's export
  as the forecast.
- It never discharges into the grid.

With a flat fixed price this reduces to plain self-consumption ("nul op de meter").

### Assumptions behind the defaults (researched November 2026, enter your own offers)

| Item | Default | Source |
|---|---|---|
| Net metering | ends 1 Jan 2027; until 2030 the feed-in compensation is at least 50 % of the bare supply price | rijksoverheid.nl, consumentenbond.nl |
| Energy tax 2027 (proposal) | € 0.1065/kWh, € 0.7457/m³ incl. VAT | eigenhuis.nl, frankenergie.nl (Belastingplan 2027, not final) |
| Dynamic markup / fee | € 0.02/kWh, € 7/month, no feed-in fee | jeroen.nl comparison: 1.8–2.3 ct, € 6–8.50/month |
| Fixed 2027 feed-in | € 0.09 compensation − € 0.06 feed-in costs | energievergelijk.nl, 18 Nov 2026 |
| Fixed price | € 0.27/kWh, gas € 1.72/m³ | estimate; gas is the ACM median for 2+ years, Nov 2026 |
| Battery | 85 % round trip, 10 W standby, 10 years | Consumentenbond 85–90 %; Marstek 6000 cycles / 10 years warranty |
| 2029 network tariff | € 0.17/kWh at weight 1.0, fixed part −€ 240/yr | ACM draft codebesluit of 8 Oct 2026 (consultation until 18 Nov 2026, final early 2027, start 1 Jan 2029) |

The ACM draft weights, per local start hour, are the default values of the two `input_text` helpers:

- **Winter (Oct–Mar):** 0.48 overnight and during the day, 0.65 at 16:00, 1.0 from 17:00 to 22:00, 0.65 at 22:00.
- **Summer (Apr–Sep):** 0.48 at night, 0.31 from 06:00 to 10:00, **0** from 10:00 to 17:00, 0.31 at 17:00, 0.65 from 18:00 to 24:00.

The proposal turns 67 % of the transport tariff into a €/kWh charge on consumption. The fixed part drops
from about € 360 to € 120 per year. Edit the weights when the final decision is published.

## Installation

### 1. EnergyZero integration (prices)

Settings → Devices & services → Add integration → **EnergyZero**. It needs no account.

Open its options (cogwheel) and set **Electricity price interval** to **Quarter-hourly**. The package
reads `sensor.energyzero_today_energy_current_hour_price` and
`sensor.energyzero_today_gas_current_hour_price`, and calls `energyzero.get_energy_prices`.

### 2. Check the entity IDs

Check these in **Developer Tools → States**. If any differ, find-and-replace them in the package:

| Entity | Role |
|---|---|
| `sensor.p1_meter_energy_import` / `_export` | HomeWizard P1 totals (all tariffs) |
| `sensor.p1_meter_power` | grid power, negative = export |
| `sensor.steca_inverter_ac_power` | solar power (W), integrated to `sensor.hb_solar_energy` |
| `sensor.gas_meter_gas` | gas meter (m³) |
| `sensor.life_the_universe_and_everything_charge_energy_added` | Tesla, used for the EV share of the breakdown |
| `sensor.bathroom_group_power`, `sensor.airco_*_energy` | breakdown only, from the bathroom and airco packages |

### 3. Package and dashboard

1. Copy `packages/home_battery.yaml` to `/config/packages/`. The `homeassistant: packages:` include is
   the same as for the other packages.
2. Developer Tools → YAML → **Check configuration**, then **Restart**.
3. The settings initialise once with the defaults above. Enter your own offers on the
   **Battery & contract** view.
4. New dashboard → Raw configuration editor → paste `dashboard_home_battery.yaml`.

The first live projection appears after 7 days. *Reset statistics* restarts all running totals, for
example after you change the battery settings. The daily cost graphs then show one negative bar.

### 4. Energy Analyzer add-on (year simulation)

1. Copy the folder `addon/energy_analyzer` to the HA `addons` share, giving `\\homeassistant.local\addons\energy_analyzer\`
   (Samba add-on). Copy `config.yaml`, `Dockerfile`, `requirements.txt` and the `energy_analyzer/` package.

   **"Not enough space" error from Explorer:** the endpoint DLP software on this laptop attaches a hidden
   stream (`sec.endpointdlp`, up to about 5 KB) to every file. Samba stores it as an ext4 extended attribute,
   and that fails above about 4 KB, which Samba reports as "disk full". Copy only the file contents instead,
   from the repository root:

   ```powershell
   @'
   import pathlib
   src = pathlib.Path(r"projects\home-assistant\home_battery\addon\energy_analyzer")
   dst = pathlib.Path(r"\\homeassistant.local\addons\energy_analyzer")
   for f in sorted(src.rglob("*")):
       if f.is_file() and "__pycache__" not in f.parts:
           (dst / f.relative_to(src)).parent.mkdir(parents=True, exist_ok=True)
           (dst / f.relative_to(src)).write_bytes(f.read_bytes())
   '@ | .\.venvs\home-assistant\Scripts\python.exe -
   ```
2. Settings → Add-ons → Add-on store → ⋮ → **Check for updates** → *Local add-ons* → **Energy Analyzer** → Install.
3. Check the options. The defaults are the P1 import/export and gas statistics; `run_at` is `04:15`. Start the add-on.
   MQTT must be set up, as for the water meter.
4. After about 2 minutes it runs the first simulation. The first run fetches a year of prices and takes
   about a minute; the prices are cached in `/data`. It publishes `sensor.energy_analyzer_status` (all
   results as attributes), one €/yr sensor per scenario, and `button.energy_analyzer_run`.

The add-on reads the helper values at every run. After changing a setting, press **Run year simulation now**.

## Reading the result

The **Verdict** card uses the year simulation once it exists, otherwise the live projection, and says
which one. For 2027 and 2029 it shows:

- the cheapest option;
- what dynamic saves or costs compared with fixed, without a battery;
- the battery's saving and payback on each contract, against the lifetime you entered.

The **Battery size** table shows whether a smaller or larger battery pays back better.

Things that are deliberately **not** modelled. They can tip a close call:

- **Battery wear.** Capacity fade is not modelled; *Min. Spread* stands in for wear on grid charging.
- **Trading.** Batteries that trade on the imbalance market (for example Zonneplan Nexus) can earn more
  than this self-use strategy. The simulated battery never exports.
- **Curtailment.** With a dynamic contract you could switch off the inverter at negative prices. The
  dashboard shows the kWh and € exported at negative prices.
- **VAT refund on a battery.** It is possible as a VAT entrepreneur with an energy management system and
  a dynamic contract (Belastingdienst "thuisbatterij btw"). Lower the investment if that applies to you.
- **Hybrid heat pump.** A dynamic contract could make the Daikin hybrid switch between gas and heat pump
  by price. Gas is compared at today's use only.
- **Resolution.** The year simulation is hourly (quarter-hour prices averaged); the live part runs per
  minute on quarter-hour prices.

## Tests

```powershell
Push-Location .\projects\home-assistant\home_battery
try { & ..\..\..\.venvs\home-assistant\Scripts\python.exe -m pytest -q }
finally { Pop-Location }
```

- `tests/test_home_battery.py` runs the package in a real HA core with a mocked EnergyZero.
- `tests/test_energy_analyzer.py` tests the add-on's simulation and wiring.
