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
from app.services.subnational_gdp.metros import load_metros
from app.services.subnational_gdp.us_metros import load_us_metros


@pytest.fixture(scope="module")
def df():
    return load_entities()


@pytest.fixture(scope="module")
def metros():
    return load_metros()


@pytest.fixture(scope="module")
def us_metros():
    return load_us_metros()


@pytest.fixture(scope="module")
def names(df):
    n = {r.entity_id: r.name for r in df[df.kind == "country"].itertuples()}
    n["USA"] = "United States"
    return n


@pytest.fixture(scope="module")
def country_places(metros, names):
    return model.country_places(metros, names)


@pytest.fixture(scope="module")
def state_places(us_metros, df):
    return model.state_places(us_metros, df)


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


# --- metro punch-out / hinterland (ticket 0008) --------------------------------
def _metros_of(places, pid):
    return next(p["metros"] for p in places if p["id"] == pid)


def test_remove_largest_and_capital_distinct_for_us(country_places):
    us = _metros_of(country_places, "USA")
    largest = model.select_removed_metros(us, remove_capital=False, remove_largest=True)
    assert [r["name"] for r in largest] == ["New York (Greater)"]
    both = model.select_removed_metros(us, remove_capital=True, remove_largest=True)
    assert {r["name"] for r in both} == {"New York (Greater)", "Washington (Greater)"}


def test_capital_equals_largest_falls_back_to_second(country_places):
    # UK: London is both capital and largest -> "both" must also drop the next-largest.
    uk = _metros_of(country_places, "GBR")
    both = model.select_removed_metros(uk, remove_capital=True, remove_largest=True)
    assert len(both) == 2
    assert "London" in {r["name"] for r in both}
    ranked = sorted(uk, key=lambda r: r["gdp_share_pct"], reverse=True)
    assert {r["name"] for r in both} == {ranked[0]["name"], ranked[1]["name"]}


def test_hinterland_us_robust_europe_fragile(country_places):
    # The crux of the debate: removing global cities barely dents US per-capita but
    # sharply cuts Paris-dependent France.
    whole = model.hinterland_table(country_places, "per_capita", False, False).set_index("entity_id")
    both = model.hinterland_table(country_places, "per_capita", True, True).set_index("entity_id")
    us_drop = 1 - both.loc["USA", "value"] / whole.loc["USA", "value"]
    fr_drop = 1 - both.loc["FRA", "value"] / whole.loc["FRA", "value"]
    assert us_drop < 0.05            # US loses < 5%
    assert fr_drop > us_drop * 2     # France loses much more
    assert "Paris" in both.loc["FRA", "removed"]


def test_hinterland_unknown_basis_raises(country_places):
    with pytest.raises(ValueError):
        model.hinterland_table(country_places, "bananas", True, False)


def test_richest_metro_and_three_way_fallback(country_places):
    us = _metros_of(country_places, "USA")
    # Richest US metro by GDP/capita is San Francisco (Greater).
    richest = model.select_removed_metros(us, remove_capital=False, remove_largest=False,
                                          remove_richest=True)
    assert "San Francisco (Greater)" in {r["name"] for r in richest}
    # All three toggles -> three distinct metros (NYC largest, DC capital, SF richest).
    three = model.select_removed_metros(us, remove_capital=True, remove_largest=True,
                                        remove_richest=True)
    assert len({r["code"] for r in three}) == 3
    names = {r["name"] for r in three}
    assert {"New York (Greater)", "Washington (Greater)", "San Francisco (Greater)"} == names


def test_three_toggles_always_distinct_count(country_places):
    # Even where capital == largest == richest, three toggles remove three metros.
    for p in country_places:
        n = len(model.select_removed_metros(p["metros"], True, True, True))
        assert n == min(3, len(p["metros"]))


# --- per-US-state punch-out (ticket 0008 phase 2) ------------------------------
def test_state_metros_use_broad_csa_footprint(us_metros):
    # New York's largest metro is the NY-Newark CSA (incl. the Hudson Valley), not
    # just the CBSA — a CSA footprint comparable to OECD's broad FUAs.
    ny = us_metros[us_metros["state_usps"] == "NY"].sort_values("in_state_gdp", ascending=False)
    top = ny.iloc[0]
    assert top["metro_level"] == "CSA"
    assert "New York" in top["metro_name"]
    assert top["in_state_gdp"] > 1.5e12        # > $1.5T in-state


def test_state_capital_vs_largest(state_places):
    # New York: capital metro (Albany) is distinct from largest (NYC) -> both removes two.
    ny = _metros_of(state_places, "US-NY")
    both = model.select_removed_metros(ny, remove_capital=True, remove_largest=True)
    names = {r["name"].split(",")[0] for r in both}
    assert any("New York" in n for n in names)
    assert any("Albany" in n for n in names)


def test_state_hinterland_strips_nyc_from_new_york(state_places):
    whole = model.hinterland_table(state_places, "per_capita", False, False).set_index("entity_id")
    largest = model.hinterland_table(state_places, "per_capita", False, True).set_index("entity_id")
    # Removing metro NYC from NY State lowers its per-capita (NYC is above the state mean).
    assert largest.loc["US-NY", "value"] < whole.loc["US-NY", "value"]
    assert all(k == "state" for k in whole["kind"])


def test_combined_ladder_has_states_and_countries(country_places, state_places):
    table = model.hinterland_table(country_places + state_places, "per_capita", True, True)
    kinds = set(table["kind"])
    assert kinds == {"state", "country"}
    assert "US-NY" in set(table["entity_id"]) and "FRA" in set(table["entity_id"])
