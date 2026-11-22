"""Tests for the Energy Analyzer year simulation (addon/energy_analyzer/energy_analyzer)."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from energy_analyzer.ha import PriceCache, build_hours, settings_from_states
from energy_analyzer.model import (
    GRID_WINTER, Battery, Contract, GridTariff, Hour, battery_step, horizon_ends, parse_profile, simulate,
    year_summary,
)

TZ = ZoneInfo("Europe/Amsterdam")
LOSSLESS = Battery(capacity_kwh=5, power_kw=2, round_trip=1.0, standby_w=0, min_spread=0.05)


def winter_day_prices(hour: int) -> float:
    """Market price incl. VAT: cheap night, expensive evening."""
    return 0.05 if hour < 6 else 0.35 if 17 <= hour < 21 else 0.15


def days_of_hours(days: int, start: dt.date = dt.date(2026, 1, 5), solar: bool = False) -> list[Hour]:
    hours = []
    for d in range(days):
        for h in range(24):
            t = dt.datetime.combine(start + dt.timedelta(days=d), dt.time(h), TZ)
            exp = 1.5 if solar and 11 <= h < 15 else 0.0
            hours.append(Hour(t=t, imp=0.0 if exp else 0.5, exp=exp, market=winter_day_prices(h), gas=0.1,
                              gas_market=0.40))
    return hours


def test_self_consumption_stores_surplus_and_covers_import_within_power_and_losses() -> None:
    b = Battery(capacity_kwh=5, power_kw=2, round_trip=0.81, standby_w=0)  # 90 % each way
    soc, imp, exp, charge, grid, dis = battery_step(b, 0.0, 0.0, 3.0, 1.0)
    assert (charge, grid, exp) == (2.0, 0.0, pytest.approx(1.0))  # power limit
    assert soc == pytest.approx(1.8)
    soc, imp, exp, charge, grid, dis = battery_step(b, soc, 2.0, 0.0, 1.0)
    assert dis == pytest.approx(1.62) and imp == pytest.approx(0.38) and soc == pytest.approx(0.0)


def test_flat_price_strategy_equals_self_consumption() -> None:
    plain = battery_step(LOSSLESS, 3.0, 0.7, 0.0, 1.0)
    smart = battery_step(LOSSLESS, 3.0, 0.7, 0.0, 1.0, p_now=0.27, future=[0.27] * 20, load_kw=0.5)
    assert smart == plain


def test_smart_charges_from_grid_when_cheap_and_holds_for_the_evening() -> None:
    future = [0.16] * 4 + [0.46] * 4 + [0.26] * 4
    soc, imp, exp, charge, grid, dis = battery_step(LOSSLESS, 1.0, 0.5, 0.0, 1.0, 0.16, future, load_kw=0.5)
    assert grid == 2.0 and dis == 0.0 and imp == 2.5 and soc == 3.0
    # Solar surplus expected later today fills the room for free: no grid charge.
    *_, grid, dis = battery_step(LOSSLESS, 1.0, 0.5, 0.0, 1.0, 0.16, future, load_kw=0.5, expected_surplus=4.0)
    assert grid == 0.0    # Full battery, stored energy covers only the expensive slots: hold it at a mid price.
    _, imp, *_, dis = battery_step(LOSSLESS, 5.0, 0.5, 0.0, 1.0, 0.26, [0.26] + [0.46] * 12, 0.5)
    assert dis == 0.0 and imp == 0.5
    _, imp, *_, dis = battery_step(LOSSLESS, 2.0, 0.5, 0.0, 1.0, 0.46, [0.46, 0.46, 0.46, 0.46, 0.26], 0.5)
    assert dis == 0.5 and imp == 0.0


def test_horizon_includes_tomorrow_only_after_publication() -> None:
    hours = days_of_hours(2)
    ends = horizon_ends(hours)
    assert ends[12] == 24 and ends[13] == 48 and ends[30] == 48


def test_winter_battery_only_pays_on_dynamic_and_2029_tariff_adds_evening_cost() -> None:
    hours = days_of_hours(14)
    contract = Contract(energy_tax=0.11, dyn_markup=0.0)
    grid = GridTariff(rate=0.25)
    res = simulate(hours, contract, grid, LOSSLESS)["total"]
    # No surplus and a flat price: a fixed-contract battery cannot earn anything.
    assert res["fixed_2027"]["battery"].cost == pytest.approx(res["fixed_2027"]["none"].cost)
    assert res["fixed_2027"]["battery"].grid_charge == 0
    # Night charging for the evening peak saves money on a dynamic contract.
    assert res["dynamic_2027"]["battery"].grid_charge > 0
    assert res["dynamic_2027"]["battery"].cost < res["dynamic_2027"]["none"].cost - 5
    # 2029: winter evening weight 1.0 makes the same import dearer; a fixed-contract battery now shifts too.
    assert res["fixed_2029"]["none"].cost > res["fixed_2027"]["none"].cost
    assert res["fixed_2029"]["battery"].cost < res["fixed_2029"]["none"].cost


def test_year_summary_annualises_and_adds_fixed_costs() -> None:
    hours = days_of_hours(14, dt.date(2026, 6, 1), solar=True)
    contract = Contract(fixed_monthly=10, dyn_monthly=5, gas_fixed=1.5, gas_markup=0.05, gas_tax=0.75)
    grid = GridTariff(fixed_change=-240)
    s = year_summary(hours, contract, grid, Battery(), lifetime_years=10)
    assert s["days"] == 14 and len(s["months"]) == 1
    no_bat = simulate(hours, contract, grid, Battery(), with_battery=False)["total"]
    assert s["annual"]["fixed_2027"]["none"] == round(no_bat["fixed_2027"]["none"].cost * 8760 / len(hours) + 120)
    assert s["annual"]["fixed_2029"]["none"] == round(no_bat["fixed_2029"]["none"].cost * 8760 / len(hours) - 120)
    assert s["gas"]["m3"] == round(0.1 * 8760) and s["gas"]["fixed"] == round(0.1 * 8760 * 1.5 + 84)
    assert s["gas_dynamic_saving"] == s["gas"]["fixed"] - s["gas"]["dynamic"]
    assert s["battery"]["fixed_2027"]["solar_charge"] > 0
    assert {r["kwh"] for r in s["sizes"]} == {2.5, 5.0, 7.5, 10.0, 15.0}
    assert s["best"]["2027"] in {f"{t}_{k}" for t in ("fixed_2027", "dynamic_2027") for k in ("none", "battery")}
    assert year_summary(hours[:100], contract, grid, Battery()) is None


def test_grid_profile_parsing_falls_back_on_bad_input() -> None:
    assert parse_profile(",".join(["1"] * 24), GRID_WINTER) == (1.0,) * 24
    assert parse_profile("1,2,3", GRID_WINTER) == GRID_WINTER
    assert parse_profile("x" * 5, GRID_WINTER) == GRID_WINTER
    assert GridTariff(rate=0.2).import_add(dt.datetime(2029, 1, 10, 18, tzinfo=TZ)) == pytest.approx(0.2)
    assert GridTariff(rate=0.2).import_add(dt.datetime(2029, 7, 10, 12, tzinfo=TZ)) == 0.0


def test_hours_need_a_price_and_use_the_latest_gas_price(tmp_path) -> None:
    t0 = int(dt.datetime(2026, 3, 1, tzinfo=TZ).timestamp())
    prices = PriceCache(tmp_path / "prices.json")
    prices.electricity = {t0: 0.1, t0 + 3600: 0.2}
    prices.gas = {t0 - 7 * 3600: 1.1, t0 + 3600: 1.2}
    changes = {"i": {t0: 1.0, t0 + 3600: 2.0, t0 + 7200: 3.0}, "e": {t0 + 3600: 0.5}, "g": {t0: 0.2}}
    hours = build_hours(changes, {"import": "i", "export": "e", "gas": "g"}, prices, TZ)
    assert [(h.imp, h.exp, h.gas, h.market, h.gas_market) for h in hours] == [
        (1.0, 0.0, 0.2, 0.1, 1.1), (2.0, 0.5, 0.0, 0.2, 1.2)]


def test_settings_come_from_package_helpers() -> None:
    states = {"input_number.hb_battery_capacity": {"state": "10"}, "input_number.hb_battery_efficiency": {"state": "90"},
              "input_boolean.hb_dynamic_export_vat": {"state": "on"}, "input_number.hb_grid_rate": {"state": "0.2"},
              "input_number.hb_battery_lifetime": {"state": "15"}, "input_number.hb_fixed_price": {"state": "x"}}
    battery, contract, grid, lifetime = settings_from_states(states)
    assert battery.capacity_kwh == 10 and battery.round_trip == 0.9 and contract.dyn_export_vat
    assert grid.rate == 0.2 and lifetime == 15 and contract.fixed_import == Contract().fixed_import


class FakeHA:
    """Statistics for 40 days and EnergyZero answering any period."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.statistics: dict[str, list] = {}

    def import_statistics(self, statistic_id, name, unit, rows):
        self.statistics[statistic_id] = rows

    def time_zone(self):
        return TZ

    def states(self):
        return {"sensor.hb_electricity_prices": {"state": "192", "attributes": {"config_entry": "abc"}}}

    def hourly_changes(self, ids, start, end):
        t0 = int((end - dt.timedelta(days=40)).timestamp())
        hours = range(t0, int(end.timestamp()), 3600)
        return {ids[0]: {t: 0.5 for t in hours}, ids[1]: {t: 0.2 for t in hours}, ids[2]: {t: 0.1 for t in hours}}

    missing: dt.date | None = None

    def service(self, domain, service, data):
        """Like EnergyZero: start..end are local dates, inclusive; a day without data fails the call."""
        self.calls.append((service, data))
        first, last = (dt.date.fromisoformat(data[k]) for k in ("start", "end"))
        if self.missing and first <= self.missing <= last:
            raise RuntimeError("HTTP 400 no_data")
        start = dt.datetime.combine(first, dt.time(), TZ)
        end = dt.datetime.combine(last + dt.timedelta(days=1), dt.time(), TZ)
        step = 86400 if service == "get_gas_prices" else 3600
        times = range(int(start.timestamp()), int(end.timestamp()), step)
        return {"prices": [{"timestamp": str(dt.datetime.fromtimestamp(t, dt.timezone.utc)), "price": 0.2}
                           for t in times]}


def test_run_fetches_prices_in_chunks_once_and_reports(tmp_path) -> None:
    from energy_analyzer.service import Options, run

    ha = FakeHA()
    result = run(ha, Options(), tmp_path)
    assert result["status"] == "ok" and result["days"] == 40
    assert "only 40 days of history" in result["notes"][0]
    assert {c[0] for c in ha.calls} == {"get_energy_prices", "get_gas_prices"}
    assert all(c[1]["config_entry"] == "abc" for c in ha.calls)
    assert len(ha.calls) == 2 * 12  # prices for all 365 days (not only the 40 with meter data), 31-day chunks
    history = result["price_history"]
    assert len(history["months"]) in (12, 13) and history["statistics"] == "ok" and history["fixed"] == 0.27
    assert history["months"][0]["dynamic_your_use"] is None  # before the meter history
    assert history["months"][-1]["dynamic_your_use"] == pytest.approx(0.2 + 0.02 + 0.1065)
    assert len(ha.statistics["electricity_dynamic"]) == 365 * 24 and ha.statistics["gas_fixed"][0][1] == 1.72
    ha.calls.clear()
    assert run(ha, Options(), tmp_path)["status"] == "ok"
    assert ha.calls == []  # everything cached


def test_a_day_without_prices_is_skipped_not_fatal(tmp_path) -> None:
    from energy_analyzer.service import Options, run

    ha = FakeHA()
    ha.missing = dt.date.today() - dt.timedelta(days=20)
    result = run(ha, Options(), tmp_path)
    assert result["status"] == "ok" and result["days"] == 39
    assert any("24 hours without a price" in n for n in result["notes"])
    ha.calls.clear()
    run(ha, Options(), tmp_path)
    assert ha.calls == []  # the missing day is remembered, not fetched every night


def test_run_without_energyzero_explains() -> None:
    from energy_analyzer.service import Options, run

    class NoPrices(FakeHA):
        def states(self):
            return {}

    assert run(NoPrices(), Options(), None)["status"] == "no EnergyZero config entry"


def test_price_history_weights_dynamic_price_by_your_use() -> None:
    from energy_analyzer.model import price_history, price_statistics

    t0 = dt.datetime(2026, 3, 1, tzinfo=TZ)
    ts = [int((t0 + dt.timedelta(hours=i)).timestamp()) for i in range(4)]
    electricity = dict(zip(ts, [0.10, 0.30, -0.05, 0.20]))
    gas = {ts[0] - 3600: 1.0}
    hours = [Hour(t=t0 + dt.timedelta(hours=1), imp=2.0, exp=0.0, market=0.30),
             Hour(t=t0 + dt.timedelta(hours=2), imp=0.0, exp=1.0, market=-0.05)]
    contract = Contract(dyn_markup=0.02, energy_tax=0.1, dyn_export_vat=True, gas_markup=0.1, gas_tax=0.7)
    (row,) = price_history(electricity, gas, hours, contract, TZ, dt.date(2026, 3, 1), dt.date(2026, 3, 31))
    assert row["dynamic"] == pytest.approx(0.1375 + 0.12) and row["market"] == pytest.approx(0.1375)
    assert row["dynamic_your_use"] == pytest.approx(0.42)  # only the expensive hour was used
    assert row["export_your_use"] == pytest.approx(-0.05) and row["negative_hours"] == 1
    assert row["gas_dynamic"] == pytest.approx(1.8) and row["import_kwh"] == 2
    series = price_statistics(electricity, gas, contract, ts[1], ts[3])
    assert series["electricity_dynamic"] == [(ts[1], 0.42), (ts[2], 0.07)]
    assert series["electricity_fixed"] == [(ts[1], 0.27), (ts[2], 0.27)]

def synthetic_weather(days: int, start: dt.date) -> dict[int, tuple[float, float]]:
    """Cold-to-hot sweep of daily mean temperatures, 6 degC daily swing, a clear-sky-like sun curve."""
    import math
    weather = {}
    for d in range(days):
        mean = -2 + 30 * d / max(days - 1, 1)
        for h in range(24):
            t = dt.datetime.combine(start + dt.timedelta(days=d), dt.time(h), TZ)
            temp = mean + 3 * math.sin(math.pi * (h - 9) / 12)
            gti = max(0.0, 800 * math.sin(math.pi * (h - 6) / 13)) * (0.5 + 0.5 * ((d * 7) % 5) / 4)
            weather[int(t.timestamp())] = (temp, gti)
    return weather


def metered_from(weather, base=8.0, heat=1.5, cool=2.0, k=3.5, gas_base=0.6, gas_heat=0.25):
    from energy_analyzer.estimate import degree_days

    dd = degree_days(weather, TZ)
    hours, solar = [], {}
    for ts, (_, gti) in sorted(weather.items()):
        t = dt.datetime.fromtimestamp(ts, TZ)
        hdd, cdd = dd[t.date()]
        use = base / 24 + heat * hdd * (0.06 if 6 <= t.hour < 18 else 0.0233) + cool * cdd * (0.1 if 12 <= t.hour < 22 else 0)
        sun = k * gti / 1000
        solar[ts] = sun
        hours.append(Hour(t=t, imp=max(use - sun, 0), exp=max(sun - use, 0), market=0.2,
                          gas=(gas_base + gas_heat * hdd) / 24, gas_market=1.0))
    return hours, solar


def test_fit_recovers_known_use_solar_and_gas_parameters() -> None:
    from energy_analyzer.estimate import Site, fit, synthesize

    weather = synthetic_weather(60, dt.date(2026, 3, 1))
    hours, solar = metered_from(weather)
    site = Site(52.0, 5.0, kwp=4.1)
    model = fit(hours, solar, weather, TZ, site)
    assert model.solar_k == pytest.approx(3.5, rel=1e-6)
    assert (model.base, model.heat, model.cool) == pytest.approx((8.0, 1.5, 2.0), rel=0.01)
    assert (model.gas_base, model.gas_heat) == pytest.approx((0.6, 0.25), rel=0.01)
    assert model.use_error_pct < 1 and model.fit_days == 60
    # The fitted model rebuilds the metered hours: same import/export per hour.
    rebuilt = synthesize(model, [int(h.t.timestamp()) for h in hours], weather, {int(h.t.timestamp()): 0.2 for h in hours},
                         {0: 1.0}, TZ, site)
    assert all(r.estimated for r in rebuilt)
    assert sum(r.imp for r in rebuilt) == pytest.approx(sum(h.imp for h in hours), rel=0.02)
    assert sum(r.exp for r in rebuilt) == pytest.approx(sum(h.exp for h in hours), rel=0.02)
    assert fit(hours[:24 * 10], solar, weather, TZ, site) is None  # fewer than 14 full days


def test_weather_irradiance_is_moved_to_the_hour_it_was_measured_in(monkeypatch) -> None:
    import io
    import json

    from energy_analyzer import estimate

    seen = {}

    def fake_urlopen(url, timeout):
        seen["url"] = url
        body = {"hourly": {"time": [0, 3600, 7200], "temperature_2m": [1.0, 2.0, None],
                           "global_tilted_irradiance": [10.0, 20.0, 30.0]}}
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(estimate.urllib.request, "urlopen", fake_urlopen)
    weather = estimate.fetch_weather(estimate.Site(52.3456, 4.8765, tilt=35, azimuth=-22),
                                     dt.date(2026, 1, 1), dt.date(2026, 1, 2))
    assert weather == {0: (1.0, 20.0), 3600: (2.0, 30.0)}  # mean over 00-01 is reported at 01:00
    assert "latitude=52.35" in seen["url"] and "azimuth=-22" in seen["url"] and "tilt=35" in seen["url"]


def test_run_estimates_the_months_before_the_meter_history(tmp_path) -> None:
    from energy_analyzer.service import Options, run

    class WithSolar(FakeHA):
        def config(self):
            return {"latitude": 52.0, "longitude": 5.0, "time_zone": "Europe/Amsterdam"}

        def hourly_changes(self, ids, start, end):
            out = super().hourly_changes(ids, start, end)
            out["sensor.steca_inverter_energy_production"] = {t: 0.1 for t in out[ids[0]]}
            return out

    def fake_fetch(site, first, last):
        weather = synthetic_weather((last - first).days + 1, first)
        return weather

    result = run(WithSolar(), Options(), tmp_path, fetch=fake_fetch)
    assert result["status"] == "ok" and result["estimate"]["status"] == "ok"
    assert result["measured_days"] == 40 and result["days"] >= 355  # the archive lags a few days
    assert result["settings"]["statistics"]["solar"] == "sensor.steca_inverter_energy_production"
    estimated = [m for m in result["months"] if m["estimated"] == 100]
    assert len(estimated) >= 9
    assert any("estimated from the weather" in n for n in result["notes"])
