"""Home battery and energy contract year simulation on measured hourly grid data.

Replays the last year of hourly P1 import/export (and gas) under four electricity tariffs:

    fixed_2027     fixed price, no net metering, a feed-in compensation and feed-in costs
    dynamic_2027   day-ahead market price + markup + energy tax, export at the market price
    fixed_2029     fixed_2027 + a time-dependent network tariff (assumed, see GridTariff)
    dynamic_2029   dynamic_2027 + the same network tariff

each without and with a virtual battery. The battery runs one price-aware strategy on the import
price of the tariff it is simulated for (see battery_step); with a flat price it reduces to plain
self-consumption (charge on surplus, discharge to cover import). The same rules run per minute in
the Home Assistant package (packages/home_battery.yaml); keep them in step.
"""
from __future__ import annotations

import bisect
import dataclasses
import datetime as dt
import math
from collections import defaultdict

TARIFFS = ("fixed_2027", "dynamic_2027", "fixed_2029", "dynamic_2029")
VAT = 1.21
SIZES_KWH = (2.5, 5.0, 7.5, 10.0, 15.0)
LOAD_WINDOW_H = 168  # trailing hours for the typical-load estimate
PUBLISH_HOUR = 13    # day-ahead prices for tomorrow are known from about this local hour


@dataclasses.dataclass
class Battery:
    capacity_kwh: float = 5.0   # usable
    power_kw: float = 2.4       # charge and discharge, AC side
    round_trip: float = 0.85    # AC to AC
    standby_w: float = 10.0     # own consumption, always from the grid
    min_spread: float = 0.05    # EUR/kWh a grid charge must earn after losses (covers wear)
    investment: float = 3000.0  # installed, EUR

    @property
    def eta(self) -> float:
        return math.sqrt(min(max(self.round_trip, 0.01), 1.0))

    def scaled(self, capacity_kwh: float) -> "Battery":
        """Same product stacked: power, standby and price scale with capacity."""
        f = capacity_kwh / self.capacity_kwh
        return dataclasses.replace(self, capacity_kwh=capacity_kwh, power_kw=self.power_kw * f,
                                   standby_w=self.standby_w * f, investment=self.investment * f)


WINTER_MONTHS = (1, 2, 3, 10, 11, 12)
# Hourly weights (index = local start hour) of ACM's draft codebesluit of 8 Oct 2026 for time-dependent
# network tariffs on small connections from 1 Jan 2029; consultation version, not final.
GRID_WINTER = (0.48,) * 16 + (0.65,) + (1.0,) * 5 + (0.65, 0.48)
GRID_SUMMER = (0.48,) * 6 + (0.31,) * 4 + (0.0,) * 7 + (0.31,) + (0.65,) * 6


def parse_profile(text: str | None, default: tuple[float, ...]) -> tuple[float, ...]:
    """24 comma-separated weights; anything else falls back to the default."""
    try:
        values = tuple(float(v) for v in (text or "").replace(";", ",").split(","))
    except ValueError:
        return default
    return values if len(values) == 24 else default


@dataclasses.dataclass
class GridTariff:
    """Assumed time-dependent network tariff (2029): rate x hourly weight per imported kWh.

    Export carries no network tariff. fixed_change is the yearly change of the fixed network part
    (about EUR 360 today, about EUR 120 in the proposal), so 2029 totals compare with 2027 ones.
    """
    rate: float = 0.17                 # EUR/kWh at weight 1.0
    winter: tuple[float, ...] = GRID_WINTER
    summer: tuple[float, ...] = GRID_SUMMER
    fixed_change: float = -240.0       # EUR/year

    def import_add(self, t: dt.datetime) -> float:
        return self.rate * (self.winter if t.month in WINTER_MONTHS else self.summer)[t.hour]


@dataclasses.dataclass
class Contract:
    """Defaults: late-2026 market (energy tax 2027 proposal, typical offers); set your own offers."""
    fixed_import: float = 0.27        # EUR/kWh all-in (supply + energy tax + VAT)
    fixed_feed_in: float = 0.09       # EUR/kWh paid for export
    fixed_feed_in_cost: float = 0.06  # EUR/kWh feed-in costs (terugleverkosten)
    fixed_monthly: float = 7.0        # EUR/month supply fixed costs, electricity
    dyn_markup: float = 0.02          # EUR/kWh incl. VAT on top of the market price
    energy_tax: float = 0.1065        # EUR/kWh incl. VAT (2027 proposal)
    dyn_feed_in_fee: float = 0.0      # EUR/kWh deducted from the export price
    dyn_export_vat: bool = False      # export paid at the market price incl. VAT
    dyn_monthly: float = 7.0          # EUR/month supply fixed costs, electricity
    gas_fixed: float = 1.72           # EUR/m3 all-in
    gas_markup: float = 0.08          # EUR/m3 incl. VAT on top of the gas market price
    gas_tax: float = 0.7457           # EUR/m3 incl. VAT (2027 proposal)
    gas_fixed_monthly: float = 7.0
    gas_dyn_monthly: float = 7.0

    def prices(self, tariff: str, market: float, t: dt.datetime, grid: GridTariff) -> tuple[float, float]:
        """(import, export) EUR/kWh. market is the day-ahead price incl. VAT."""
        if tariff.startswith("fixed"):
            imp, exp = self.fixed_import, self.fixed_feed_in - self.fixed_feed_in_cost
        else:
            imp = market + self.dyn_markup + self.energy_tax
            exp = (market if self.dyn_export_vat else market / VAT) - self.dyn_feed_in_fee
        if tariff.endswith("2029"):
            imp += grid.import_add(t)
        return imp, exp

    def yearly_fixed(self, tariff: str, grid: GridTariff) -> float:
        fee = 12 * (self.fixed_monthly if tariff.startswith("fixed") else self.dyn_monthly)
        return fee + (grid.fixed_change if tariff.endswith("2029") else 0.0)


@dataclasses.dataclass
class Hour:
    t: dt.datetime            # local, tz-aware hour start
    imp: float                # kWh imported
    exp: float                # kWh exported
    market: float             # EUR/kWh day-ahead incl. VAT
    gas: float = 0.0          # m3
    gas_market: float | None = None  # EUR/m3 incl. VAT
    estimated: bool = False   # synthesised from weather (estimate.py), not metered


def battery_step(b: Battery, soc: float, imp: float, exp: float, hours: float, p_now: float | None = None,
                 future: list[float] | None = None, load_kw: float = 0.4, slot_h: float = 1.0,
                 expected_surplus: float = 0.0):
    """One step of the virtual battery behind the meter.

    imp/exp: metered kWh in the step without battery. future: import prices of the known slots
    from now to the end of the day-ahead horizon (current slot first); None = self-consumption.
    expected_surplus: kWh of solar surplus expected within the horizon; it counts as stored energy
    for the hold rule and as room that grid charging leaves free.
    Returns (soc, imp, exp, solar_charge, grid_charge, discharge), energies in kWh.

    Rules: always store surplus. Cover import only when the current price is among the n most
    expensive known slots, n = slots the stored plus expected energy lasts at the typical load. Charge from the
    grid when the current price is among the cheapest slots needed to fill up (minus the room kept
    for expected surplus) and the expected value (mean of the most expensive slots one full
    battery covers) after losses beats it by at least min_spread. Never discharge into the grid.
    """
    eta = b.eta
    e_max = b.power_kw * hours
    charge = min(exp, e_max, max(b.capacity_kwh - soc, 0.0) / eta)
    soc += charge * eta
    grid = 0.0
    allow = True
    if future and p_now is not None:
        desc = sorted(future, reverse=True)
        per_slot = max(load_kw * slot_h, 1e-6)
        n_d = max(1, math.ceil((soc + expected_surplus * eta) * eta / per_slot))
        allow = p_now >= desc[min(n_d, len(desc)) - 1] - 1e-9
        room = b.capacity_kwh - soc - expected_surplus * eta
        if room > 1e-6 and e_max - charge > 1e-9:
            n_c = max(1, math.ceil(room / (eta * b.power_kw * slot_h)))
            threshold = desc[-min(n_c, len(desc))]
            top = desc[:max(1, math.ceil(b.capacity_kwh * eta / per_slot))]
            value = sum(top) / len(top)
            if p_now <= threshold + 1e-9 and value * b.round_trip - p_now >= b.min_spread:
                grid = min(e_max - charge, room / eta)
                soc += grid * eta
                allow = False
    discharge = min(imp, max(e_max - charge - grid, 0.0), soc * eta) if allow else 0.0
    soc -= discharge / eta
    return soc, imp - discharge + grid + b.standby_w / 1000 * hours, exp - charge, charge, grid, discharge


@dataclasses.dataclass
class Totals:
    cost: float = 0.0
    imp: float = 0.0
    exp: float = 0.0
    solar_charge: float = 0.0
    grid_charge: float = 0.0
    discharge: float = 0.0

    def add(self, cost: float, imp: float, exp: float, sc: float = 0.0, gc: float = 0.0, dis: float = 0.0) -> None:
        self.cost += cost
        self.imp += imp
        self.exp += exp
        self.solar_charge += sc
        self.grid_charge += gc
        self.discharge += dis


def horizon_ends(hours: list[Hour]) -> list[int]:
    """Index after the last hour whose price is known at each hour (rest of today, plus tomorrow from 13:00)."""
    starts = [h.t.timestamp() for h in hours]
    ends = []
    for h in hours:
        days = 2 if h.t.hour >= PUBLISH_HOUR else 1
        midnight = dt.datetime.combine(h.t.date() + dt.timedelta(days=days), dt.time(), h.t.tzinfo)
        ends.append(bisect.bisect_left(starts, midnight.timestamp()))
    return ends


def simulate(hours: list[Hour], contract: Contract, grid: GridTariff, battery: Battery,
             with_battery: bool = True) -> dict:
    """Totals and per-month totals per tariff, without ("none") and with ("battery") battery."""
    ends = horizon_ends(hours)
    prices = {t: [contract.prices(t, h.market, h.t, grid) for h in hours] for t in TARIFFS}
    export_at = {int(h.t.timestamp()): h.exp for h in hours}
    total = {t: {"none": Totals(), "battery": Totals()} for t in TARIFFS}
    months: dict[str, dict] = defaultdict(lambda: {t: {"none": Totals(), "battery": Totals()} for t in TARIFFS})
    soc = dict.fromkeys(TARIFFS, 0.0)
    neg = Totals()
    recent: list[float] = []
    for i, h in enumerate(hours):
        load = max(sum(recent) / len(recent), 0.1) if len(recent) >= 24 else 0.4
        recent.append(h.imp)
        if len(recent) > LOAD_WINDOW_H:
            recent.pop(0)
        month = months[h.t.strftime("%Y-%m")]
        # Persistence forecast: yesterday's export over the price horizon (at most 24 h ahead).
        yesterday = int(h.t.timestamp()) - 86400
        surplus = sum(export_at.get(yesterday + k * 3600, 0.0) for k in range(min(ends[i] - i, 24))) \
            if with_battery else 0.0
        for t in TARIFFS:
            imp_p, exp_p = prices[t][i]
            for target in (total[t]["none"], month[t]["none"]):
                target.add(h.imp * imp_p - h.exp * exp_p, h.imp, h.exp)
            if not with_battery:
                continue
            future = [p[0] for p in prices[t][i:ends[i]]]
            soc[t], b_imp, b_exp, sc, gc, dis = battery_step(battery, soc[t], h.imp, h.exp, 1.0, imp_p, future, load,
                                                             expected_surplus=surplus)
            for target in (total[t]["battery"], month[t]["battery"]):
                target.add(b_imp * imp_p - b_exp * exp_p, b_imp, b_exp, sc, gc, dis)
        _, dyn_exp = prices["dynamic_2027"][i]
        if dyn_exp < 0 and h.exp > 0:
            neg.add(-h.exp * dyn_exp, 0.0, h.exp)
    return {"total": total, "months": dict(months), "negative_export": neg}


def gas_costs(hours: list[Hour], contract: Contract) -> dict:
    m3 = fixed = dynamic = 0.0
    last = None
    for h in hours:
        last = h.gas_market if h.gas_market is not None else last
        if last is None:
            continue
        m3 += h.gas
        fixed += h.gas * contract.gas_fixed
        dynamic += h.gas * (last + contract.gas_markup + contract.gas_tax)
    return {"m3": m3, "fixed": fixed, "dynamic": dynamic}


def _payback(investment: float, saving: float) -> float | None:
    return round(investment / saving, 1) if saving > 0 else None


def year_summary(hours: list[Hour], contract: Contract, grid: GridTariff, battery: Battery,
                 lifetime_years: float = 12.0) -> dict | None:
    """Annualised comparison; costs per year include the monthly supply fees."""
    if len(hours) < 7 * 24:
        return None
    scale = 8760 / len(hours)
    sim = simulate(hours, contract, grid, battery)
    annual, battery_info = {}, {}
    for t in TARIFFS:
        fee = contract.yearly_fixed(t, grid)
        none, bat = sim["total"][t]["none"], sim["total"][t]["battery"]
        annual[t] = {"none": round(none.cost * scale + fee), "battery": round(bat.cost * scale + fee),
                     "import_none": round(none.imp * scale), "export_none": round(none.exp * scale),
                     "import_battery": round(bat.imp * scale), "export_battery": round(bat.exp * scale)}
        saving = (none.cost - bat.cost) * scale
        battery_info[t] = {"saving": round(saving), "payback": _payback(battery.investment, saving),
                           "lifetime_gain": round(saving * lifetime_years - battery.investment),
                           "cycles": round(bat.discharge / battery.eta / battery.capacity_kwh * scale),
                           "solar_charge": round(bat.solar_charge * scale),
                           "grid_charge": round(bat.grid_charge * scale),
                           "discharge": round(bat.discharge * scale)}
    gas = gas_costs(hours, contract)
    gas_scale = 8760 / len(hours)
    gas_annual = {"m3": round(gas["m3"] * gas_scale),
                  "fixed": round(gas["fixed"] * gas_scale + 12 * contract.gas_fixed_monthly),
                  "dynamic": round(gas["dynamic"] * gas_scale + 12 * contract.gas_dyn_monthly)}
    months = []
    estimated = defaultdict(int)
    per_month = defaultdict(int)
    for h in hours:
        per_month[h.t.strftime("%Y-%m")] += 1
        estimated[h.t.strftime("%Y-%m")] += h.estimated
    for key in sorted(sim["months"]):
        m = sim["months"][key]
        n = m["fixed_2027"]["none"]
        months.append({"month": key, "import": round(n.imp), "export": round(n.exp),
                       "estimated": round(100 * estimated[key] / per_month[key]),
                       **{f"{t}_{k}": round(m[t][k].cost, 1) for t in TARIFFS for k in ("none", "battery")}})
    sizes = []
    for cap in sorted({*SIZES_KWH, battery.capacity_kwh}):
        b = battery.scaled(cap)
        res = simulate(hours, contract, grid, b)["total"]
        row = {"kwh": cap, "kw": round(b.power_kw, 1), "investment": round(b.investment)}
        for t in TARIFFS:
            saving = (res[t]["none"].cost - res[t]["battery"].cost) * scale
            row[t] = round(saving)
            row[f"{t}_payback"] = _payback(b.investment, saving)
        sizes.append(row)
    options = {f"{t}_{k}": annual[t][k] for t in TARIFFS for k in ("none", "battery")}
    best = {y: min((k for k in options if y in k), key=options.get) for y in ("2027", "2029")}
    neg = sim["negative_export"]
    return {
        "hours": len(hours), "days": round(len(hours) / 24),
        "measured_days": round(sum(not h.estimated for h in hours) / 24),
        "period_start": hours[0].t.date().isoformat(), "period_end": hours[-1].t.date().isoformat(),
        "annual": annual, "battery": battery_info, "gas": gas_annual, "best": best,
        "dynamic_saving_2027": annual["fixed_2027"]["none"] - annual["dynamic_2027"]["none"],
        "dynamic_saving_2029": annual["fixed_2029"]["none"] - annual["dynamic_2029"]["none"],
        "gas_dynamic_saving": gas_annual["fixed"] - gas_annual["dynamic"],
        "negative_export_kwh": round(neg.exp * scale), "negative_export_cost": round(neg.cost * scale),
        "months": months, "sizes": sizes,
    }


def price_history(electricity: dict[int, float], gas: dict[int, float], hours: list[Hour], contract: Contract,
                  tz, first: dt.date, last: dt.date) -> list[dict]:
    """Per month: dynamic 2027 prices (plain average and weighted by your metered use) and gas.

    electricity/gas: hour start epoch -> market price incl. VAT (gas: the latest published price applies).
    """
    used = {int(h.t.timestamp()): h for h in hours}
    gas_times = sorted(gas)
    rows: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for ts in sorted(electricity):
        t = dt.datetime.fromtimestamp(ts, tz)
        if not first <= t.date() <= last:
            continue
        r = rows[t.strftime("%Y-%m")]
        market = electricity[ts]
        imp_p, exp_p = contract.prices("dynamic_2027", market, t, GridTariff())
        r["n"] += 1
        r["market"] += market
        r["dynamic"] += imp_p
        r["negative"] += market < 0
        if (h := used.get(ts)) is not None:
            r["imp"] += h.imp
            r["imp_cost"] += h.imp * imp_p
            r["exp"] += h.exp
            r["exp_value"] += h.exp * exp_p
        k = bisect.bisect_right(gas_times, ts) - 1
        if k >= 0:
            r["gas_n"] += 1
            r["gas"] += gas[gas_times[k]]
    out = []
    for month in sorted(rows):
        r = rows[month]
        out.append({
            "month": month, "hours": int(r["n"]), "market": round(r["market"] / r["n"], 4),
            "dynamic": round(r["dynamic"] / r["n"], 4),
            "dynamic_your_use": round(r["imp_cost"] / r["imp"], 4) if r["imp"] > 0 else None,
            "export_your_use": round(r["exp_value"] / r["exp"], 4) if r["exp"] > 0 else None,
            "import_kwh": round(r["imp"]), "negative_hours": int(r["negative"]),
            "gas_dynamic": round(r["gas"] / r["gas_n"] + contract.gas_markup + contract.gas_tax, 3)
            if r["gas_n"] else None,
        })
    return out


def price_statistics(electricity: dict[int, float], gas: dict[int, float], contract: Contract,
                     first_ts: float, end_ts: float) -> dict[str, list[tuple[int, float]]]:
    """Hourly all-in prices for HA long-term statistics: (hour start epoch, EUR per kWh or m3)."""
    gas_times = sorted(gas)
    out: dict[str, list[tuple[int, float]]] = {"electricity_dynamic": [], "electricity_fixed": [],
                                               "gas_dynamic": [], "gas_fixed": []}
    for ts in sorted(electricity):
        if not first_ts <= ts < end_ts:
            continue
        out["electricity_dynamic"].append((ts, round(electricity[ts] + contract.dyn_markup + contract.energy_tax, 5)))
        out["electricity_fixed"].append((ts, contract.fixed_import))
        k = bisect.bisect_right(gas_times, ts) - 1
        if k >= 0:
            out["gas_dynamic"].append((ts, round(gas[gas_times[k]] + contract.gas_markup + contract.gas_tax, 4)))
            out["gas_fixed"].append((ts, contract.gas_fixed))
    return out
