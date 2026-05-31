"""Tests for same-year alignment / smoothing (ticket 0009).

The core ``estimate_metric`` logic is tested on synthetic series (no network, no
parquet) so the interpolation/extrapolation/eligibility rules are pinned exactly.
A few integration tests run against the committed time-series parquet when present.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.services.subnational_gdp import estimate as E
from app.services.subnational_gdp import model


# --- core metric estimator (synthetic, pure) ----------------------------------
def test_exact_actual_not_flagged():
    actual = {2020: 100.0, 2022: 121.0}
    val, est, anchor = E.estimate_metric(actual, {}, 2020)
    assert val == 100.0 and est is False and anchor == 2020


def test_interpolation_is_log_linear():
    # 100 (2020) -> 144 (2022); the log-linear midpoint 2021 is the geometric mean 120.
    actual = {2020: 100.0, 2022: 144.0}
    val, est, anchor = E.estimate_metric(actual, {}, 2021)
    assert est is True and anchor is None
    assert math.isclose(val, 120.0, rel_tol=1e-9)


def test_forward_extrapolation_uses_imf_growth():
    # Last actual 2024; IMF says +10% 2024->2025. Carry the actual, not the IMF level.
    actual = {2022: 90.0, 2023: 95.0, 2024: 100.0}
    imf = {2024: 50.0, 2025: 55.0}  # IMF level differs; only its ratio (1.10) matters
    val, est, anchor = E.estimate_metric(actual, imf, 2025)
    assert est is True and anchor == 2024
    assert math.isclose(val, 110.0, rel_tol=1e-9)


def test_forward_extrapolation_cagr_fallback_without_imf():
    actual = {2022: 100.0, 2024: 121.0}  # CAGR = 10%/yr
    val, est, anchor = E.estimate_metric(actual, {}, 2025)
    assert est is True and anchor == 2024
    assert math.isclose(val, 121.0 * 1.10, rel_tol=1e-9)


def test_no_value_beyond_forward_horizon():
    actual = {2018: 100.0, 2020: 110.0}  # last actual 2020
    # 2025 is 5 years past -> beyond FORWARD_HORIZON -> no value.
    val, est, anchor = E.estimate_metric(actual, {2020: 1.0, 2025: 2.0}, 2025)
    assert val is None


def test_back_extrapolation_within_horizon():
    actual = {2010: 121.0, 2012: 146.41}  # 10%/yr
    val, est, anchor = E.estimate_metric(actual, {}, 2009)
    assert est is True and anchor == 2010
    assert math.isclose(val, 110.0, rel_tol=1e-6)


def test_single_actual_no_growth_signal_returns_none():
    # One point, no IMF -> can't establish a trend -> no extrapolation.
    val, est, anchor = E.estimate_metric({2024: 100.0}, {}, 2025)
    assert val is None


def test_empty_series():
    assert E.estimate_metric({}, {}, 2025) == (None, False, None)


# --- entities_for_year eligibility + derived flags (synthetic frame) -----------
def _ts_row(eid, name, kind, region, year, metric, value, source):
    return dict(entity_id=eid, name=name, kind=kind, parent=eid if kind == "country" else "USA",
                region=region, year=year, metric=metric, value=value, source=source)


@pytest.fixture
def synthetic_ts():
    rows = []
    # FRESHLAND: nominal + ppp + pop all observed to 2024 (worldbank), IMF to 2025.
    for y, v in {2022: 80, 2023: 90, 2024: 100}.items():
        rows.append(_ts_row("FRS", "Freshland", "country", "Europe", y, "gdp_nominal_usd", v * 1e9, "worldbank"))
        rows.append(_ts_row("FRS", "Freshland", "country", "Europe", y, "gdp_ppp_usd", v * 1.2e9, "worldbank"))
        rows.append(_ts_row("FRS", "Freshland", "country", "Europe", y, "population", 10e6, "worldbank"))
    rows.append(_ts_row("FRS", "Freshland", "country", "Europe", 2024, "gdp_nominal_usd", 100e9, "imf"))
    rows.append(_ts_row("FRS", "Freshland", "country", "Europe", 2025, "gdp_nominal_usd", 105e9, "imf"))
    rows.append(_ts_row("FRS", "Freshland", "country", "Europe", 2024, "gdp_ppp_usd", 120e9, "imf"))
    rows.append(_ts_row("FRS", "Freshland", "country", "Europe", 2025, "gdp_ppp_usd", 126e9, "imf"))
    rows.append(_ts_row("FRS", "Freshland", "country", "Europe", 2024, "population", 10e6, "imf"))
    rows.append(_ts_row("FRS", "Freshland", "country", "Europe", 2025, "population", 10.1e6, "imf"))
    # STALELAND: everything stops in 2021 -> must vanish at 2025.
    for y in (2019, 2020, 2021):
        rows.append(_ts_row("STL", "Staleland", "country", "Africa", y, "gdp_nominal_usd", 5e9, "worldbank"))
        rows.append(_ts_row("STL", "Staleland", "country", "Africa", y, "population", 2e6, "worldbank"))
    return pd.DataFrame(rows)


def test_eligibility_drops_stale_entity_at_2025(synthetic_ts):
    df = E.entities_for_year(synthetic_ts, 2025)
    ids = set(df.entity_id)
    assert "FRS" in ids
    assert "STL" not in ids        # no data within the horizon -> not invented


def test_stale_entity_present_when_year_is_within_its_data(synthetic_ts):
    df = E.entities_for_year(synthetic_ts, 2021).set_index("entity_id")
    assert "STL" in df.index
    assert df.loc["STL", "gdp_nominal_usd_estimated"] == False  # actual in 2021


def test_extrapolated_2025_is_flagged(synthetic_ts):
    df = E.entities_for_year(synthetic_ts, 2025).set_index("entity_id")
    r = df.loc["FRS"]
    assert r["gdp_nominal_usd_estimated"] == True
    # 100bn carried +5% via IMF ratio
    assert math.isclose(r["gdp_nominal_usd"], 105e9, rel_tol=1e-9)


def test_actual_year_not_flagged(synthetic_ts):
    df = E.entities_for_year(synthetic_ts, 2023).set_index("entity_id")
    r = df.loc["FRS"]
    assert r["gdp_nominal_usd_estimated"] == False
    assert math.isclose(r["gdp_nominal_usd"], 90e9, rel_tol=1e-9)


def test_median_scaled_and_flagged(synthetic_ts):
    # vintage 2023 median, asked at 2025 -> scaled by PPP-per-capita growth, flagged.
    med = pd.DataFrame([{"entity_id": "FRS", "median_income_ppp_usd": 30000.0,
                         "rural_median_ppp_usd": 25000.0, "year": 2023}])
    df = E.entities_for_year(synthetic_ts, 2025, med).set_index("entity_id")
    r = df.loc["FRS"]
    assert r["median_income_estimated"] == True
    assert r["median_income_year"] == 2023
    # PPP-per-capita grew from 108bn/10m (2023 actual) to 126bn/10.1m (2025 est, IMF).
    pc23 = 108e9 / 10e6
    pc25 = 126e9 / 10.1e6
    assert math.isclose(r["median_income_ppp_usd"], 30000.0 * pc25 / pc23, rel_tol=1e-6)


# --- integration against the committed parquet (skipped if not built) ----------
def _have_ts():
    try:
        E.load_timeseries()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.filterwarnings("ignore")
needs_ts = pytest.mark.skipif(not _have_ts(), reason="timeseries parquet not built")


@needs_ts
def test_available_years_reasonable():
    lo, hi = E.available_years()
    assert lo == 1997 and 2024 <= hi <= 2026


@needs_ts
def test_2025_table_ranks_and_flags():
    df = E.load_entities_for_year(2025)
    t = model.ranked_table(df, "ppp", ("state", "country"))
    assert len(t) > 150
    # Countries are mostly extrapolated to 2025 (WB lags); US states are BEA-actual.
    assert df.loc[df.entity_id == "DEU", "gdp_nominal_usd_estimated"].iloc[0] == True
    assert df.loc[df.entity_id == "US-CA", "gdp_nominal_usd_estimated"].iloc[0] == False
