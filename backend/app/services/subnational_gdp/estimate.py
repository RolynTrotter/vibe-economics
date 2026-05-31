"""Same-year alignment by interpolation / short-horizon extrapolation (ticket 0009).

Given the long time-series table (``timeseries.load_timeseries``) and a **target
year**, produce the wide, one-row-per-place table the model/UI consume — every
place expressed on the *same* year — with each figure flagged ``actual`` or
``estimated``.

Method (per place, per metric — nominal GDP, PPP GDP, population — independently)
--------------------------------------------------------------------------------
Let the *actuals* be the observed World Bank / BEA values (IMF is never spliced as a
level — only used for its near-term growth). For a target year ``Y``:

1. **Exact** — ``Y`` is observed: use it (not flagged).
2. **Interpolate** — ``Y`` falls between two actuals: log-linear interpolation
   (constant-growth between the brackets). Flagged estimated. This is the easy
   "2023 from 2022 & 2024" case.
3. **Extrapolate forward** — ``Y`` is past the last actual, by at most
   ``FORWARD_HORIZON`` years: grow the last actual by IMF WEO year-on-year growth
   when available (so a country whose GDP stops at 2024 is carried to 2025 by the
   IMF's 2024→2025 path), else by the place's own recent CAGR. Flagged estimated.
4. **Extrapolate back** — symmetric, before the first actual, within ``BACK_HORIZON``.
5. Otherwise **no value** (``None``).

Eligibility falls out of the horizons: a place whose *every* metric stops more than
``FORWARD_HORIZON`` years before ``Y`` yields ``None`` everywhere and simply drops
out for that year — we don't presume where an economy ended up when nobody (not
even the IMF) has data near that year. Derived bases (per-capita) are estimated if
either input is; median income is scaled by PPP-per-capita growth from its own
vintage to ``Y``.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .timeseries import DATASET_ID as TS_DATASET_ID
from .timeseries import load_timeseries

# How far past the last actual (or before the first) we are willing to carry a place.
# Two years keeps the 2025 alignment honest: a place must have been observed by ~2023.
FORWARD_HORIZON = 2
BACK_HORIZON = 2
# Years of history used for the CAGR fallback when IMF growth isn't available.
CAGR_WINDOW = 5

METRICS = ("gdp_nominal_usd", "gdp_ppp_usd", "population")
ACTUAL_SOURCES = frozenset({"bea", "worldbank"})


def _cagr(series: dict[int, float], window: int = CAGR_WINDOW) -> float | None:
    """Annual compound growth over the last `window` years of `series` (>=2 points)."""
    yrs = sorted(series)
    if len(yrs) < 2:
        return None
    recent = yrs[-(window + 1):] if len(yrs) > window else yrs
    y0, y1 = recent[0], recent[-1]
    v0, v1 = series[y0], series[y1]
    if v0 <= 0 or v1 <= 0 or y1 == y0:
        return None
    return (v1 / v0) ** (1.0 / (y1 - y0)) - 1.0


def _interp_log(series: dict[int, float], lo: int, hi: int, target: int) -> float:
    """Log-linear (constant-growth) interpolation of `series` between lo and hi."""
    v_lo, v_hi = series[lo], series[hi]
    frac = (target - lo) / (hi - lo)
    return float(np.exp(np.log(v_lo) + frac * (np.log(v_hi) - np.log(v_lo))))


def _extrapolate(actual: dict[int, float], imf: dict[int, float],
                 anchor: int, target: int) -> float | None:
    """Carry actual[anchor] to `target` (either direction) using IMF growth if the
    whole path is covered, else the place's own CAGR. None if neither is possible."""
    # IMF growth chain: needs both endpoints (ratio is robust to level differences).
    if imf and anchor in imf and target in imf and imf[anchor] > 0:
        return actual[anchor] * (imf[target] / imf[anchor])
    g = _cagr(actual)
    if g is None:
        return None
    return actual[anchor] * (1.0 + g) ** (target - anchor)


def estimate_metric(actual: dict[int, float], imf: dict[int, float],
                    target: int) -> tuple[float | None, bool, int | None]:
    """(value, is_estimated, anchor_year) for one metric at `target`.

    `anchor_year` is the year of the actual the estimate leans on (the observed year
    for exact/extrapolated values; None for interpolation between two actuals).
    """
    if not actual:
        return None, False, None
    yrs = sorted(actual)
    lo, hi = yrs[0], yrs[-1]
    if target in actual:
        return actual[target], False, target
    if lo < target < hi:
        below = max(y for y in yrs if y < target)
        above = min(y for y in yrs if y > target)
        return _interp_log(actual, below, above, target), True, None
    if target > hi and (target - hi) <= FORWARD_HORIZON:
        val = _extrapolate(actual, imf, hi, target)
        return (val, True, hi) if val is not None else (None, False, None)
    if target < lo and (lo - target) <= BACK_HORIZON:
        val = _extrapolate(actual, imf, lo, target)
        return (val, True, lo) if val is not None else (None, False, None)
    return None, False, None


def _split_sources(g: pd.DataFrame, metric: str) -> tuple[dict[int, float], dict[int, float]]:
    """Return (actuals, imf) {year: value} dicts for one entity+metric."""
    sub = g[g["metric"] == metric]
    actual = {int(r.year): float(r.value)
              for r in sub[sub["source"].isin(ACTUAL_SOURCES)].itertuples()}
    imf = {int(r.year): float(r.value)
           for r in sub[sub["source"] == "imf"].itertuples()}
    return actual, imf


def entities_for_year(ts: pd.DataFrame, target_year: int,
                      median_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Wide one-row-per-place table aligned to `target_year`, with estimated flags.

    Columns: entity_id, name, kind, parent, region, year, and for each metric the
    value plus ``<metric>_estimated`` / ``<metric>_anchor_year``. Places with no
    value on *any* metric at `target_year` are dropped. When `median_df` is given,
    the median-income columns are carried to the target year by PPP-per-capita growth.
    """
    median_lookup = {}
    if median_df is not None:
        median_lookup = {r.entity_id: r for r in median_df.itertuples()}

    rows = []
    for entity_id, g in ts.groupby("entity_id", sort=False):
        first = g.iloc[0]
        rec = {
            "entity_id": entity_id, "name": first["name"], "kind": first["kind"],
            "parent": first["parent"], "region": first["region"], "year": target_year,
        }
        series_actual: dict[str, dict[int, float]] = {}
        series_imf: dict[str, dict[int, float]] = {}
        any_value = False
        for metric in METRICS:
            actual, imf = _split_sources(g, metric)
            series_actual[metric] = actual
            series_imf[metric] = imf
            value, est, anchor = estimate_metric(actual, imf, target_year)
            rec[metric] = value
            rec[f"{metric}_estimated"] = bool(est) if value is not None else False
            rec[f"{metric}_anchor_year"] = anchor
            if value is not None:
                any_value = True
        if not any_value:
            continue

        # Median income: scale the vintage figure to target_year by PPP-per-capita
        # growth (a level we already estimate on both ends).
        rec["median_income_ppp_usd"] = None
        rec["median_income_estimated"] = False
        rec["median_income_year"] = None
        rec["rural_median_ppp_usd"] = None
        rec["rural_median_estimated"] = False
        mrow = median_lookup.get(entity_id)
        if mrow is not None:
            _apply_median(rec, mrow, series_actual, series_imf, target_year)
        rows.append(rec)

    out = pd.DataFrame(rows)
    return out.sort_values("gdp_nominal_usd", ascending=False, na_position="last").reset_index(drop=True)


def _ppp_per_capita_at(series_actual: dict[str, dict[int, float]],
                       series_imf: dict[str, dict[int, float]], year: int) -> float | None:
    """Estimated PPP GDP per capita at `year` (for scaling median income), or None.

    Uses the same IMF-aware estimates as the main table so the median's anchor moves
    consistently with the GDP/population figures shown beside it."""
    ppp_v, _, _ = estimate_metric(series_actual.get("gdp_ppp_usd", {}),
                                  series_imf.get("gdp_ppp_usd", {}), year)
    pop_v, _, _ = estimate_metric(series_actual.get("population", {}),
                                  series_imf.get("population", {}), year)
    if ppp_v is None or not pop_v:
        return None
    return ppp_v / pop_v


def _apply_median(rec: dict, mrow, series_actual: dict[str, dict[int, float]],
                  series_imf: dict[str, dict[int, float]], target_year: int) -> None:
    """Carry the median-income vintage to target_year by PPP-per-capita growth."""
    vintage = int(mrow.year) if mrow.year is not None else None
    if vintage is None:
        return
    rec["median_income_year"] = vintage
    estimated = target_year != vintage
    factor: float | None = 1.0
    if estimated:
        pc_t = _ppp_per_capita_at(series_actual, series_imf, target_year)
        pc_v = _ppp_per_capita_at(series_actual, series_imf, vintage)
        factor = (pc_t / pc_v) if (pc_t and pc_v) else None  # None -> can't scale

    def scaled(base) -> float | None:
        if base is None or factor is None or (isinstance(base, float) and np.isnan(base)):
            return None
        return float(base) * factor

    rec["median_income_ppp_usd"] = scaled(getattr(mrow, "median_income_ppp_usd", None))
    rec["rural_median_ppp_usd"] = scaled(getattr(mrow, "rural_median_ppp_usd", None))
    rec["median_income_estimated"] = estimated and rec["median_income_ppp_usd"] is not None
    rec["rural_median_estimated"] = estimated and rec["rural_median_ppp_usd"] is not None


# --------------------------------------------------------------------------- #
# Cached convenience for the router (snapshot path stays in data.load_entities)
# --------------------------------------------------------------------------- #
def available_years(ts: pd.DataFrame | None = None) -> tuple[int, int]:
    """(min, max) target years offered. Max = latest year any place has an actual."""
    ts = ts if ts is not None else load_timeseries()
    actual = ts[ts["source"].isin(ACTUAL_SOURCES)]
    lo = int(actual["year"].min())
    hi = int(actual["year"].max())
    return max(lo, 1997), hi  # states begin 1997; clamp the floor there


@lru_cache(maxsize=64)
def _cached_entities_for_year(target_year: int) -> pd.DataFrame:
    ts = load_timeseries()
    median_df = None
    try:
        from .median_income import load_median_income
        median_df = load_median_income()
    except (FileNotFoundError, KeyError, ImportError):
        median_df = None
    return entities_for_year(ts, target_year, median_df)


def load_entities_for_year(target_year: int) -> pd.DataFrame:
    """Router entry point: aligned wide table for `target_year` (cached)."""
    return _cached_entities_for_year(target_year).copy()
