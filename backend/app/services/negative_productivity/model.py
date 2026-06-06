"""Pure analysis for the negative-productivity service — localized-inflation lens.

No I/O here: every function takes the tidy CPI long table (year, month, category,
cpi_index) from data.py and returns plain Python / DataFrames. The router and the
static exporter both call these, so the deployed snapshot and the API agree.

Core quantities, per month:
- **headline**   12-month % change in "All items".
- **dispersion** cross-sectional standard deviation of the six major groups'
  12-month % changes (population std, ddof=0) — the "localized inflation" gauge.
- **spread**     hottest minus coldest category (percentage points).
- **skew**       Pearson moment skewness of the category cross-section. Ball &
  Mankiw (1995): positive skew (a few categories spiking up) is the fingerprint of
  an adverse supply shock and pushes headline inflation up.
- **hottest / coldest** the category at each tail.

Everything is in **percentage points** (e.g. 7.4 means 7.4% YoY).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import CATEGORIES, HEADLINE_LABEL

CATEGORY_ORDER = list(CATEGORIES.values())

# Known adverse-supply-shock episodes, for chart annotation (start, end, label).
EPISODES = [
    (1973.8, 1975.0, "OPEC I oil embargo"),
    (1979.0, 1981.0, "OPEC II / Iran"),
    (2007.5, 2008.6, "Oil & food spike"),
    (2021.2, 2023.0, "Pandemic supply chains"),
]


def _moment_skew(values: np.ndarray) -> float:
    """Pearson moment skewness g1 = m3 / m2**1.5 (population moments). 0 if degenerate."""
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if v.size < 3:
        return 0.0
    d = v - v.mean()
    m2 = (d ** 2).mean()
    m3 = (d ** 3).mean()
    if m2 <= 0:
        return 0.0
    return float(m3 / m2 ** 1.5)


def yoy_wide(df: pd.DataFrame) -> pd.DataFrame:
    """Wide table indexed by (year, month) of 12-month % change, one column per series.

    Columns are the category labels plus the headline label; values in percentage
    points. Rows are sorted chronologically with a `t` float (year + (month-1)/12)
    for plotting.
    """
    idx = df.pivot_table(index=["year", "month"], columns="category", values="cpi_index")
    idx = idx.sort_index()
    yoy = (idx / idx.shift(12) - 1.0) * 100.0  # 12 monthly steps = one year
    yoy = yoy.reset_index()
    yoy["t"] = yoy["year"] + (yoy["month"] - 1) / 12.0
    return yoy


def dispersion_series(df: pd.DataFrame) -> list[dict]:
    """Per-month dispersion record over the six major groups.

    Only months where all available category columns are present are kept (the panel
    is the six continuous-since-1967 groups, so this is months from ~1968 on).
    """
    yoy = yoy_wide(df)
    cats = [c for c in CATEGORY_ORDER if c in yoy.columns]
    out: list[dict] = []
    for _, row in yoy.iterrows():
        vals = row[cats].to_numpy(dtype=float)
        if np.isnan(vals).any():
            continue
        hottest = cats[int(np.argmax(vals))]
        coldest = cats[int(np.argmin(vals))]
        out.append(
            {
                "t": round(float(row["t"]), 4),
                "year": int(row["year"]),
                "month": int(row["month"]),
                "label": f"{int(row['year']):04d}-{int(row['month']):02d}",
                "headline": _r(row.get(HEADLINE_LABEL)),
                "dispersion": round(float(np.std(vals, ddof=0)), 3),
                "spread": round(float(vals.max() - vals.min()), 3),
                "skew": round(_moment_skew(vals), 3),
                "hottest": hottest,
                "coldest": coldest,
            }
        )
    return out


def category_breakdown(df: pd.DataFrame) -> dict[str, list[dict]]:
    """Per-month YoY for each category, keyed by 'YYYY-MM' — powers the bar view."""
    yoy = yoy_wide(df)
    cats = [c for c in CATEGORY_ORDER if c in yoy.columns]
    out: dict[str, list[dict]] = {}
    for _, row in yoy.iterrows():
        vals = row[cats]
        if vals.isna().any():
            continue
        key = f"{int(row['year']):04d}-{int(row['month']):02d}"
        out[key] = [{"category": c, "yoy": _r(row[c])} for c in cats]
    return out


def latest_snapshot(df: pd.DataFrame) -> dict:
    """The most recent month's dispersion record + category breakdown."""
    series = dispersion_series(df)
    if not series:
        return {}
    last = series[-1]
    key = f"{last['year']:04d}-{last['month']:02d}"
    breakdown = category_breakdown(df).get(key, [])
    return {**last, "label": key, "categories": breakdown}


def _r(v) -> float | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return round(float(v), 3)
