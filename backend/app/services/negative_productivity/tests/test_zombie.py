"""Tests for the zombie-firm lens — pure model on synthetic panels."""
from __future__ import annotations

import pandas as pd

from app.services.negative_productivity import zombie_model as zm


def _panel(rows):
    """rows: list of (cik, name, year, icr). ebit/interest are back-solved (interest=1)."""
    return pd.DataFrame(
        [
            {"cik": c, "name": n, "loc": "US-XX", "year": y, "ebit": icr, "interest": 1.0, "icr": icr}
            for c, n, y, icr in rows
        ]
    )


def test_three_consecutive_sub1_flags_zombie():
    # cik 1: ICR < 1 in 2018,2019,2020 -> zombie in 2020. cik 2: healthy.
    df = _panel(
        [(1, "Zomco", 2018, 0.5), (1, "Zomco", 2019, 0.8), (1, "Zomco", 2020, 0.3)]
        + [(2, "Healthco", y, 4.0) for y in (2018, 2019, 2020)]
    )
    series = {r["year"]: r for r in zm.zombie_share_series(df)}
    assert series[2020]["n_firms"] == 2
    assert series[2020]["n_zombies"] == 1
    assert series[2020]["share"] == 50.0


def test_two_bad_years_is_not_a_zombie():
    # Only 2 consecutive sub-1 years (2019,2020); 2018 healthy -> not a zombie.
    df = _panel([(1, "Almost", 2018, 2.0), (1, "Almost", 2019, 0.5), (1, "Almost", 2020, 0.4)])
    series = {r["year"]: r for r in zm.zombie_share_series(df)}
    assert series[2020]["n_zombies"] == 0


def test_recovery_breaks_the_streak():
    # bad, bad, recover, bad -> never 3-in-a-row.
    df = _panel(
        [(1, "Phoenix", 2017, 0.4), (1, "Phoenix", 2018, 0.6),
         (1, "Phoenix", 2019, 3.0), (1, "Phoenix", 2020, 0.2)]
    )
    series = {r["year"]: r for r in zm.zombie_share_series(df)}
    assert all(r["n_zombies"] == 0 for r in series.values())


def test_mature_subset_uses_reporting_age():
    # Old firm (first seen 2009) and young firm (first seen 2018), both zombies in 2020.
    old = [(1, "OldZom", y, 0.5) for y in range(2009, 2021)]
    young = [(2, "NewZom", y, 0.5) for y in (2018, 2019, 2020)]
    df = _panel(old + young)
    s2020 = {r["year"]: r for r in zm.zombie_share_series(df)}[2020]
    assert s2020["n_zombies"] == 2          # both are zombies
    assert s2020["n_mature_zombies"] == 1   # only the ≥10y-reporting firm counts as mature


def test_latest_zombies_ranked_by_interest_burden():
    rows = []
    for cik, name, interest in [(1, "BigDebt", 500.0), (2, "SmallDebt", 5.0)]:
        for y in (2018, 2019, 2020):
            rows.append({"cik": cik, "name": name, "loc": "US-XX", "year": y,
                         "ebit": 0.5 * interest, "interest": interest, "icr": 0.5})
    df = pd.DataFrame(rows)
    out = zm.latest_zombies(df, top_n=10, mature_only=False)
    assert out["year"] == 2020
    assert [f["name"] for f in out["firms"]] == ["BigDebt", "SmallDebt"]
