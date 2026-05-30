"""Tests for the subnational-GDP comparison.

These run against the committed compiled snapshot (data/processed/subnational_gdp.parquet).
We pin *structural* facts and robust orderings rather than exact GDP figures
(which move when the dataset is rebuilt), plus the depletion-free invariants of the
ranking math.
"""
from __future__ import annotations

import math

import pytest

from app.services.subnational_gdp import model
from app.services.subnational_gdp.data import load_entities


@pytest.fixture(scope="module")
def df():
    return load_entities()


def test_coverage(df):
    # 50 states + DC, plus a broad set of countries.
    states = df[df["kind"] == "state"]
    assert len(states) == 51
    assert df[df["kind"] == "country"].shape[0] > 150
    # Every state has positive GDP and a plausible derived population.
    assert (states["gdp_nominal_usd"] > 0).all()
    assert states["population"].between(2e5, 5e7).all()  # WY ~0.58M .. CA ~39M


def test_state_ppp_equals_nominal_proxy(df):
    # US states use nominal USD as a PPP proxy (US ≈ PPP base).
    states = df[df["kind"] == "state"]
    assert (states["gdp_ppp_usd"] == states["gdp_nominal_usd"]).all()


def test_ranking_is_sorted_and_dense(df):
    t = model.ranked_table(df, "nominal")
    vals = t["value"].to_numpy()
    assert (vals[:-1] >= vals[1:]).all()                 # descending
    assert t["rank"].tolist() == list(range(1, len(t) + 1))  # dense 1..n


def test_california_is_a_top_economy(df):
    t = model.ranked_table(df, "nominal")
    ca = t[t["entity_id"] == "US-CA"].iloc[0]
    # California sits among the largest national economies on total nominal GDP.
    assert ca["rank"] <= 8
    assert 3e12 < ca["value"] < 6e12  # ~$4T, robust band


def test_per_capita_reshuffles_the_ladder(df):
    nominal = model.ranked_table(df, "nominal").set_index("entity_id")["rank"]
    percap = model.ranked_table(df, "per_capita").set_index("entity_id")["rank"]
    # The whole point of the widget: the ladder reorders by basis. Big-but-populous
    # places fall on a per-capita basis (China is the clearest example).
    chn = "CHN"
    assert percap[chn] > nominal[chn]


def test_per_capita_drops_entities_without_population(df):
    # per_capita needs population; nominal does not — so per_capita is never longer.
    assert len(model.ranked_table(df, "per_capita")) <= len(model.ranked_table(df, "nominal"))


def test_dc_excluded_from_per_capita_only(df):
    # DC's GDP/capita is a commuter artifact: present on total bases, dropped per-capita.
    nominal_ids = set(model.ranked_table(df, "nominal")["entity_id"])
    percap_ids = set(model.ranked_table(df, "per_capita")["entity_id"])
    assert "US-DC" in nominal_ids
    assert "US-DC" not in percap_ids


def test_compare_preserves_request_order(df):
    rows = model.compare(df, ["FRA", "US-CA", "DEU"], "nominal")
    assert [r["entity_id"] for r in rows] == ["FRA", "US-CA", "DEU"]
    for r in rows:
        assert r["value"] > 0 and r["rank"] >= 1


def test_nearest_finds_countries_for_a_state(df):
    res = model.nearest(df, "US-VA", "nominal", n=3, among="country")
    assert res["entity"]["entity_id"] == "US-VA"
    assert len(res["nearest"]) == 3
    assert all(n["kind"] == "country" for n in res["nearest"])
    # neighbours are ordered by closeness in value to Virginia
    target = res["entity"]["value"]
    dists = [abs(n["value"] - target) for n in res["nearest"]]
    assert dists == sorted(dists)


def test_unknown_basis_raises(df):
    with pytest.raises(ValueError):
        model.basis_value(df, "bananas")


def test_basis_value_matches_manual_per_capita(df):
    row = df[df["entity_id"] == "US-CA"].iloc[0]
    pc = model.basis_value(df, "per_capita")[df["entity_id"] == "US-CA"].iloc[0]
    assert math.isclose(pc, row["gdp_ppp_usd"] / row["population"], rel_tol=1e-9)
