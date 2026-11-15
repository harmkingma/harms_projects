import datetime as dt

import pytest

from watermeter.hpboiler import PV_PROFILE, Params, build_year, params_from_states, simulate, year_summary


def hours(year: int, month: int, export_midday: float, ndays: int = 28) -> dict[dt.datetime, float]:
    start = dt.datetime(year, month, 1)
    out = {}
    for h in range(ndays * 24):
        t = start + dt.timedelta(hours=h)
        out[t] = export_midday if 10 <= t.hour < 16 else 0.0
    return out


def share(m):
    return m.solar_el / (m.solar_el + m.grid_el)


def test_sunny_month_runs_mostly_on_solar():
    assert share(simulate(hours(2026, 6, 3.0), Params())[(2026, 6)]) > 0.9


def test_no_export_means_all_grid():
    m = simulate(hours(2026, 1, 0.0), Params())[(2026, 1)]
    assert m.solar_el == 0 and m.grid_el > 0


def test_energy_balance():
    p = Params()
    m = simulate(hours(2026, 4, 1.0), p)[(2026, 4)]
    supplied = (m.solar_el + m.grid_el) * p.cop
    needed = m.heat + p.standby_kwh_day * m.hours / 24
    assert needed <= supplied <= needed + p.tank_l * 4.186 * 55 / 3600


def test_build_year_estimates_missing_months_from_measured_pattern():
    data = hours(2026, 11, 0.5, ndays=10)
    year, info = build_year(data, dt.date(2026, 11, 20))
    assert len(info) == 12 and info[-1] == {"month": "2026-11", "source": "measured", "days": 10, "scale": 3.0}
    june = next(i for i in info if i["month"] == "2026-06")
    assert june["source"] == "estimated from 2026-11"
    assert year[dt.datetime(2026, 6, 3, 12)] == pytest.approx(0.5 * PV_PROFILE[5] / PV_PROFILE[10])
    assert year[dt.datetime(2026, 6, 3, 20)] == 0.0


def test_year_summary_needs_a_measured_month():
    assert year_summary(hours(2026, 11, 0.5, ndays=3), Params(), dt.date(2026, 11, 5)) is None
    s = year_summary(hours(2026, 11, 0.5, ndays=10), Params(), dt.date(2026, 11, 20))
    assert s["measured_months"] == 1 and len(s["months"]) == 12
    summer = next(m for m in s["months"] if m["month"] == "2026-07")
    winter = next(m for m in s["months"] if m["month"] == "2026-01")
    assert summer["solar_share"] > winter["solar_share"]


def test_params_from_states_uses_measured_demand():
    p, notes = params_from_states({"sensor.usage_tracking_days": "10", "sensor.gas_hot_water_total": "3.0",
                                   "input_number.wm_hp_boiler_tank_l": "150"})
    assert p.heat_kwh_day == pytest.approx(0.3 * 9.77 * 0.85) and p.tank_l == 150
    assert notes == ["peak session: default 7 kWh (none measured yet)"]
