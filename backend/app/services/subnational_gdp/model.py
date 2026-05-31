"""Pure analysis for the subnational-GDP comparison (ticket 0002).

No FastAPI, no I/O — every function takes the tidy entities DataFrame (from
``data.load_entities``) plus params and returns numbers/DataFrames. This is what
the tests pin.

The question: place US states and whole countries on one ranked ladder, on a
chosen **basis**, so you can see "this state ≈ that country" — and watch the
ladder reshuffle as the basis changes (a state that's a giant by total GDP can be
middling per-capita, and vice-versa).

Bases
-----
- ``nominal``     total GDP at market exchange rates (USD). The headline size.
- ``ppp``         total GDP at PPP (international $). Re-ranks toward places where
                  a dollar buys more. US-state values use nominal as a PPP proxy
                  (US ≈ PPP base); see data.py.
- ``per_capita``  GDP-PPP per person — a living-standards lens. Small, rich places
                  (Luxembourg, DC) leap up; populous lower-income countries fall.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Entities dropped from the per-capita ranking only. DC's GDP-per-capita is a
# commuter artifact: its output is produced by a metro-wide workforce but divided
# by DC residents alone, so it sits absurdly above every real economy. Excluded
# until the planned metro-aware treatment lands.
PER_CAPITA_EXCLUDE: frozenset[str] = frozenset({"US-DC"})

# basis -> (column, per_capita?, label, blurb)
BASES: dict[str, dict] = {
    "nominal": {
        "column": "gdp_nominal_usd", "per_capita": False,
        "label": "Total GDP (nominal USD)",
        "blurb": "GDP at market exchange rates — the headline size of the economy.",
    },
    "ppp": {
        "column": "gdp_ppp_usd", "per_capita": False,
        "label": "Total GDP (PPP, international $)",
        "blurb": "GDP adjusted for purchasing power. US-state figures use nominal "
                 "USD as a PPP proxy (US ≈ PPP base).",
    },
    "per_capita": {
        "column": "gdp_ppp_usd", "per_capita": True,
        "label": "GDP per capita (PPP)",
        "blurb": "PPP GDP divided by population — a living-standards lens.",
    },
}


def basis_value(df: pd.DataFrame, basis: str) -> pd.Series:
    """The comparison value per row for `basis` (NaN where inputs are missing)."""
    if basis not in BASES:
        raise ValueError(f"Unknown basis '{basis}'. Options: {list(BASES)}")
    spec = BASES[basis]
    col = df[spec["column"]].astype(float)
    if spec["per_capita"]:
        pop = df["population"].astype(float)
        return col / pop.where(pop > 0)
    return col


def ranked_table(df: pd.DataFrame, basis: str, kinds: tuple[str, ...] | None = None) -> pd.DataFrame:
    """All entities sorted desc by `basis`, with a dense 1-based rank.

    `kinds` optionally filters to e.g. ("state", "country"). Rows with no value on
    the chosen basis are dropped (so per-capita drops places lacking population).
    Columns: entity_id, name, kind, parent, value, rank, year.
    """
    out = df.copy()
    out["value"] = basis_value(out, basis)
    out = out.dropna(subset=["value"])
    if basis == "per_capita":
        out = out[~out["entity_id"].isin(PER_CAPITA_EXCLUDE)]
    if kinds is not None:
        out = out[out["kind"].isin(kinds)]
    out = out.sort_values("value", ascending=False).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    cols = ["entity_id", "name", "kind", "parent", "region", "value", "rank", "year"]
    return out[[c for c in cols if c in out.columns]]


# --------------------------------------------------------------------------- #
# Metro punch-out ("hinterland" comparison) — ticket 0008
# --------------------------------------------------------------------------- #
def select_removed_metros(
    metros: list[dict], remove_capital: bool, remove_largest: bool,
    remove_richest: bool = False,
) -> list[dict]:
    """Which metros to punch out of one *place* (country or US state), per toggles.

    `metros` is a list of metro dicts with ``code``, ``is_capital``,
    ``gdp_share_pct`` and ``per_capita``. Each checked toggle nominates one metro:
    - remove_largest  -> the top-GDP-share metro.
    - remove_capital  -> the capital metro.
    - remove_richest  -> the highest-GDP-per-capita metro.

    When picks coincide (London is capital *and* largest; the Bay Area may be
    largest *and* richest), each toggle "falls down" to the next-best in its own
    ranking, and any remaining shortfall is filled by next-largest GDP — so the
    number of distinct metros removed equals the number of toggles checked.
    """
    rows = [r for r in metros]
    if not rows:
        return []
    by_gdp = sorted(rows, key=lambda r: r["gdp_share_pct"], reverse=True)
    by_pc = sorted((r for r in rows if r.get("per_capita")),
                   key=lambda r: r["per_capita"], reverse=True)
    n_targets = sum([remove_capital, remove_largest, remove_richest])
    chosen: dict[str, dict] = {}

    if remove_largest:
        pick = next((r for r in by_gdp if r["code"] not in chosen), None)
        if pick:
            chosen[pick["code"]] = pick
    if remove_capital:
        cap = next((r for r in rows if r["is_capital"]), None)
        if cap is not None:
            chosen[cap["code"]] = cap
    if remove_richest:
        pick = next((r for r in by_pc if r["code"] not in chosen), None)
        if pick:
            chosen[pick["code"]] = pick
    # Fill any shortfall (coinciding picks, e.g. capital == largest) by next-largest.
    for r in by_gdp:
        if len(chosen) >= n_targets:
            break
        chosen.setdefault(r["code"], r)
    return list(chosen.values())


def country_places(metros: pd.DataFrame, names: dict[str, str] | None = None) -> list[dict]:
    """Build hinterland `place` dicts (one per OECD country) from the FUA table."""
    names = names or {}
    places = []
    for iso3, g in metros.groupby("country_iso3"):
        first = g.iloc[0]
        places.append({
            "id": iso3, "name": names.get(iso3, iso3), "kind": "country",
            "region": None,
            "nat_gdp_nominal_usd": None if pd.isna(first["nat_gdp_nominal_usd"]) else float(first["nat_gdp_nominal_usd"]),
            "nat_gdp_ppp_usd": float(first["nat_gdp_ppp_usd"]),
            "nat_population": float(first["nat_population"]),
            "year": int(first["year"]),
            "metros": [
                {"code": r.fua_code, "name": r.fua_name, "is_capital": bool(r.is_capital),
                 "gdp_share_pct": float(r.gdp_share_pct),
                 "population": None if pd.isna(r.fua_population) else float(r.fua_population),
                 "per_capita": (float(r.fua_gdp_ppp_usd) / float(r.fua_population))
                               if (pd.notna(r.fua_population) and r.fua_population) else None}
                for r in g.itertuples()
            ],
        })
    return places


def state_places(us_metros: pd.DataFrame, entities: pd.DataFrame) -> list[dict]:
    """Build hinterland `place` dicts (one per US state) from the CSA metro table.

    State totals come from the entities table; each metro's GDP share is its in-state
    county GDP (place of work) over state GDP, and its population is in-state county
    population (residence) — so removing it nets out cross-border commuters.
    """
    ent = entities.set_index("entity_id")
    places = []
    for usps, g in us_metros.groupby("state_usps"):
        eid = f"US-{usps}"
        if eid not in ent.index:
            continue
        name = ent.loc[eid, "name"]
        # State totals from the county series (consistent with in-state metro sums),
        # so the GDP share is exact and the hinterland is exactly the non-metro counties.
        state_gdp = float(g["state_total_gdp"].iloc[0])
        state_pop = float(g["state_total_pop"].iloc[0])
        places.append({
            "id": eid, "name": name, "kind": "state", "region": "United States",
            "nat_gdp_nominal_usd": state_gdp,
            "nat_gdp_ppp_usd": state_gdp,  # US states: PPP ≈ nominal (US ≈ PPP base)
            "nat_population": state_pop,
            "year": int(g["year"].iloc[0]),
            "metros": [
                {"code": r.metro_id, "name": r.metro_name, "is_capital": bool(r.has_state_capital),
                 "gdp_share_pct": float(r.in_state_gdp) / state_gdp * 100.0,
                 "population": float(r.in_state_pop),
                 "per_capita": (float(r.in_state_gdp) / float(r.in_state_pop))
                               if r.in_state_pop else None}
                for r in g.itertuples()
            ],
        })
    return places


def nonoecd_places(curated: pd.DataFrame, entities: pd.DataFrame) -> list[dict]:
    """Build hinterland `place` dicts for big non-OECD countries from the curated
    metro table (ticket 0008 phase 3). National totals come from the World Bank
    entities; each metro's GDP share is its (curated, nominal) metro GDP over national
    nominal GDP, and per-capita is scaled to PPP via the national PPP/nominal ratio.
    Marked ``curated=True`` so the UI can flag these as estimates."""
    ent = entities[entities.kind == "country"].set_index("entity_id")
    places = []
    for iso3, g in curated.groupby("country_iso3"):
        if iso3 not in ent.index:
            continue
        row = ent.loc[iso3]
        nat_nom = float(row["gdp_nominal_usd"])
        nat_ppp = float(row["gdp_ppp_usd"]) if pd.notna(row["gdp_ppp_usd"]) else nat_nom
        ppp_ratio = nat_ppp / nat_nom if nat_nom else 1.0
        metros = []
        for r in g.itertuples():
            pop = float(r.population)
            metros.append({
                "code": f"{iso3}-{r.metro_name[:6]}", "name": r.metro_name,
                "is_capital": bool(r.is_capital),
                "gdp_share_pct": float(r.metro_gdp_nominal_usd) / nat_nom * 100.0,
                "population": pop,
                "per_capita": (float(r.metro_gdp_nominal_usd) * ppp_ratio / pop) if pop else None,
            })
        places.append({
            "id": iso3, "name": row["name"], "kind": "country", "region": row["region"],
            "nat_gdp_nominal_usd": nat_nom, "nat_gdp_ppp_usd": nat_ppp,
            "nat_population": float(row["population"]), "year": int(row["year"]),
            "metros": metros, "curated": True,
        })
    return places


# A place whose residual population/GDP after removal is below this fraction of the
# whole is treated as having no meaningful hinterland (e.g. New Jersey or Rhode
# Island — essentially all metro). Excluded rather than shown as an unstable ratio.
MIN_RESIDUAL_FRACTION = 0.12


def hinterland_table(
    places: list[dict], basis: str, remove_capital: bool, remove_largest: bool,
    remove_richest: bool = False,
) -> pd.DataFrame:
    """Ladder of `places` (countries and/or US states) with each one's selected
    metro(s) punched out and the remainder recomputed on `basis`.

    Carve-out: rest_gdp = national × (1 − Σ metro GDP shares); rest_pop = national_pop
    − Σ metro populations. Places left with < MIN_RESIDUAL_FRACTION of their
    population *or* GDP are dropped (no real hinterland). Columns: entity_id, name,
    kind, region, value, rank, year, removed (metro names), removed_share.
    """
    if basis not in BASES:
        raise ValueError(f"Unknown basis '{basis}'. Options: {list(BASES)}")
    rows = []
    for p in places:
        removed = select_removed_metros(p["metros"], remove_capital, remove_largest, remove_richest)
        share = sum(r["gdp_share_pct"] for r in removed) / 100.0
        pop_removed = sum((r["population"] or 0.0) for r in removed)
        rest_pop = p["nat_population"] - pop_removed
        if rest_pop <= MIN_RESIDUAL_FRACTION * p["nat_population"] or share >= 1 - MIN_RESIDUAL_FRACTION:
            continue
        rest_ppp = p["nat_gdp_ppp_usd"] * (1 - share)
        if basis == "nominal":
            value = None if p["nat_gdp_nominal_usd"] is None else p["nat_gdp_nominal_usd"] * (1 - share)
        elif basis == "ppp":
            value = rest_ppp
        else:  # per_capita (PPP)
            value = rest_ppp / rest_pop
        if value is None:
            continue
        rows.append({
            "entity_id": p["id"], "name": p["name"], "kind": p["kind"],
            "region": p.get("region"), "value": value, "year": p["year"],
            "removed": [r["name"] for r in removed], "removed_share": share,
            "curated": bool(p.get("curated", False)),
        })
    out = pd.DataFrame(rows).sort_values("value", ascending=False).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def compare(df: pd.DataFrame, entity_ids: list[str], basis: str) -> list[dict]:
    """Values + global ranks for a specific set of entities on `basis`."""
    table = ranked_table(df, basis)
    sel = table[table["entity_id"].isin(entity_ids)]
    order = {e: i for i, e in enumerate(entity_ids)}
    sel = sel.sort_values("entity_id", key=lambda s: s.map(order))
    return sel.to_dict(orient="records")


def nearest(df: pd.DataFrame, entity_id: str, basis: str, n: int = 3,
            among: str = "country") -> dict:
    """For one entity, the `among`-kind neighbours closest in `basis` value.

    Powers "your state ≈ this country": pass a US-state id, get the countries whose
    economy is nearest on the chosen basis. `among` can be "country", "state", or
    "any".
    """
    table = ranked_table(df, basis)
    if entity_id not in set(table["entity_id"]):
        raise ValueError(f"Entity '{entity_id}' has no value on basis '{basis}'.")
    target = table.loc[table["entity_id"] == entity_id].iloc[0]
    pool = table[table["entity_id"] != entity_id]
    if among != "any":
        pool = pool[pool["kind"] == among]
    pool = pool.assign(distance=(pool["value"] - target["value"]).abs())
    neigh = pool.sort_values("distance").head(n)
    return {
        "entity": target[["entity_id", "name", "kind", "value", "rank", "year"]].to_dict(),
        "basis": basis,
        "nearest": neigh[["entity_id", "name", "kind", "value", "rank", "year"]].to_dict(orient="records"),
    }
