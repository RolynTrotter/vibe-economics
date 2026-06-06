"""Tests for the localized-inflation lens — pure model on synthetic CPI data."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.negative_productivity import model
from app.services.negative_productivity.data import CATEGORIES, HEADLINE_LABEL


def _synthetic(years=range(2000, 2004), shock_year=None):
    """Build a tidy CPI table. Each category compounds at a flat monthly rate so YoY
    is constant and known; optionally one category gets a one-off jump in shock_year
    to create cross-sectional dispersion."""
    rows = []
    labels = [HEADLINE_LABEL] + list(CATEGORIES.values())
    base = {lab: 100.0 for lab in labels}
    monthly = 0.01  # ~12.7% YoY flat for everyone, so baseline dispersion ≈ 0
    for y in years:
        for m in range(1, 13):
            for lab in labels:
                base[lab] *= 1 + monthly
                val = base[lab]
                if shock_year and y == shock_year and lab == "Transportation":
                    val *= 1.20 if (m == 1) else 1.0  # one big January jump
                rows.append({"year": y, "month": m, "category": lab, "cpi_index": val})
    return pd.DataFrame(rows)


def test_dispersion_zero_when_categories_move_together():
    df = _synthetic()
    series = model.dispersion_series(df)
    assert series, "expected some months"
    # After the first 12 months (needed for YoY), everyone moves identically.
    steady = [r for r in series if r["year"] >= 2001]
    assert all(abs(r["dispersion"]) < 1e-6 for r in steady)
    assert all(abs(r["spread"]) < 1e-6 for r in steady)


def test_shock_creates_dispersion_and_spread():
    df = _synthetic(years=range(2000, 2004), shock_year=2002)
    series = model.dispersion_series(df)
    shock = next(r for r in series if r["year"] == 2002 and r["month"] == 1)
    quiet = next(r for r in series if r["year"] == 2001 and r["month"] == 6)
    assert shock["dispersion"] > quiet["dispersion"]
    assert shock["spread"] > 15.0  # the +20% jump shows up as a wide spread
    assert shock["hottest"] == "Transportation"
    assert shock["skew"] > 0  # one category spiking up => positive skew


def test_skew_sign_matches_definition():
    up = model._moment_skew(np.array([1.0, 1.0, 1.0, 1.0, 9.0]))  # one high outlier
    down = model._moment_skew(np.array([1.0, 9.0, 9.0, 9.0, 9.0]))  # one low outlier
    assert up > 0 and down < 0
    assert abs(model._moment_skew(np.array([2.0, 2.0]))) == 0.0  # degenerate


def test_breakdown_and_latest_are_consistent():
    df = _synthetic(years=range(2000, 2004), shock_year=2002)
    breakdown = model.category_breakdown(df)
    snap = model.latest_snapshot(df)
    assert snap["label"] in breakdown
    # latest snapshot carries one entry per major group, in display order
    assert [c["category"] for c in snap["categories"]] == list(CATEGORIES.values())
    # headline YoY is present and finite at the latest month
    assert snap["headline"] is not None
