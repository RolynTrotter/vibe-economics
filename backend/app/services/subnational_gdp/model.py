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
    if kinds is not None:
        out = out[out["kind"].isin(kinds)]
    out = out.sort_values("value", ascending=False).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    cols = ["entity_id", "name", "kind", "parent", "region", "value", "rank", "year"]
    return out[[c for c in cols if c in out.columns]]


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
