#!/usr/bin/env python3
"""Export compiled datasets to static JSON snapshots for the deployed web app.

The GitHub Pages build is static (no backend), so widgets read pre-compiled JSON
from frontend/public/data/ instead of calling the API. Re-run this after
recompiling a dataset so the deployed app and the backend agree.

Usage (from repo root, with the backend venv):
    backend/.venv/bin/python scripts/export_static_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "frontend" / "public" / "data"


def export_jst_returns() -> None:
    df = pd.read_parquet(ROOT / "data" / "processed" / "jst_returns.parquet")
    df = df.sort_values("year")
    payload = {
        "dataset": "jst_returns",
        "source": "Jordà-Schularick-Taylor Macrohistory (Rate of Return on Everything, 1870-2015)",
        "first_year": int(df.year.min()),
        "last_year": int(df.year.max()),
        "n_years": int(len(df)),
        "units": "real (CPI-adjusted); withdrawals constant in real terms",
        "definition": (
            "SWR = upper bound on the 4% rule: max constant real withdrawal that "
            "depletes the portfolio to exactly $0 at the horizon."
        ),
        "notes": (
            "US & bond from JST USA series; intl = GDP-weighted developed-ex-US "
            "equity converted to USD. Three-fund = 60/40 equity/bond with equity "
            "split 60/40 US/intl, so it differs from 60-40 only by international "
            "diversification."
        ),
        "columns": ["year", "us_stock", "intl_stock", "bond", "inflation"],
        "rows": [
            [
                int(r.year),
                round(float(r.us_stock), 6),
                round(float(r.intl_stock), 6),
                round(float(r.bond), 6),
                round(float(r.inflation), 6),
            ]
            for r in df.itertuples()
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "jst_returns.json"
    out.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"wrote {len(payload['rows'])} rows -> {out.relative_to(ROOT)}")


def export_subnational_gdp() -> None:
    df = pd.read_parquet(ROOT / "data" / "processed" / "subnational_gdp.parquet")
    df = df.sort_values("gdp_nominal_usd", ascending=False)
    payload = {
        "dataset": "subnational_gdp",
        "sources": (
            "BEA Regional (US state GDP; population derived from personal income / "
            "per-capita personal income; public domain) + World Bank WDI (country "
            "GDP, GDP PPP, population; CC BY 4.0)."
        ),
        "bases": {
            "nominal": {
                "label": "Total GDP (nominal)",
                "blurb": "GDP at market exchange rates — the headline size.",
            },
            "ppp": {
                "label": "Total GDP (PPP)",
                "blurb": "GDP adjusted for purchasing power (international $). "
                         "US-state figures use nominal USD as a PPP proxy.",
            },
            "per_capita": {
                "label": "GDP per capita (PPP)",
                "blurb": "PPP GDP per person — a living-standards lens.",
            },
        },
        "caveats": [
            "US-state PPP uses nominal USD as a proxy (US ≈ PPP reference economy; "
            "US PPP/nominal ≈ 1.01).",
            "State population is derived (personal income ÷ per-capita personal income).",
            "DC is excluded from the per-capita ranking: its GDP-per-capita is a "
            "commuter artifact (metro-wide output divided by DC residents only).",
            "Release lags differ by source; each place carries the year of its GDP figure.",
        ],
        "entities": [
            {
                "id": r.entity_id,
                "name": r.name,
                "kind": r.kind,
                "parent": r.parent,
                "region": r.region,
                "gdp_nominal_usd": round(float(r.gdp_nominal_usd)),
                "gdp_ppp_usd": None if pd.isna(r.gdp_ppp_usd) else round(float(r.gdp_ppp_usd)),
                "population": None if pd.isna(r.population) else round(float(r.population)),
                "year": int(r.year),
            }
            for r in df.itertuples()
        ],
    }
    payload["hinterland"] = _build_hinterland(df)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "subnational_gdp.json"
    out.write_text(json.dumps(payload, separators=(",", ":")))
    nh = len(payload["hinterland"]["places"]) if payload["hinterland"] else 0
    print(f"wrote {len(payload['entities'])} entities + {nh} hinterland places -> {out.relative_to(ROOT)}")


def _round_place(p: dict) -> dict:
    """JSON-serialise a model place dict (round floats, keep keys the JS expects)."""
    return {
        "id": p["id"], "name": p["name"], "kind": p["kind"], "region": p["region"],
        "nat_gdp_nominal_usd": None if p["nat_gdp_nominal_usd"] is None else round(p["nat_gdp_nominal_usd"]),
        "nat_gdp_ppp_usd": round(p["nat_gdp_ppp_usd"]),
        "nat_population": round(p["nat_population"]),
        "year": p["year"],
        "metros": [
            {"code": m["code"], "name": m["name"], "is_capital": m["is_capital"],
             "gdp_share_pct": round(m["gdp_share_pct"], 3),
             "population": None if m["population"] is None else round(m["population"]),
             "per_capita": None if m.get("per_capita") is None else round(m["per_capita"])}
            for m in p["metros"]
        ],
    }


def _build_hinterland(entities_df: pd.DataFrame) -> dict:
    """Metro punch-out block (ticket 0008): per place (OECD country + US state), its
    totals + metros, so the widget subtracts the capital/largest metro client-side."""
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.subnational_gdp import model

    proc = ROOT / "data" / "processed"
    places = []
    if (proc / "subnational_metros.parquet").exists():
        names = {r.entity_id: r.name for r in entities_df[entities_df.kind == "country"].itertuples()}
        names["USA"] = "United States"
        cp = model.country_places(pd.read_parquet(proc / "subnational_metros.parquet"), names)
        # carry region onto countries for colouring
        regions = {r.entity_id: r.region for r in entities_df[entities_df.kind == "country"].itertuples()}
        regions["USA"] = "United States"
        for p in cp:
            p["region"] = regions.get(p["id"])
        places += cp
    if (proc / "us_state_metros.parquet").exists():
        places += model.state_places(pd.read_parquet(proc / "us_state_metros.parquet"), entities_df)

    places = [_round_place(p) for p in places]
    places.sort(key=lambda p: p["nat_gdp_ppp_usd"], reverse=True)
    return {
        "source": "OECD Functional Urban Areas (countries) + Census/OMB CSA + BEA county "
                  "GDP/population (US states). National totals: World Bank WDI / BEA.",
        "note": "Each place's capital and/or largest metro can be removed and values "
                "recomputed on the remaining hinterland. Countries: OECD FUA share of "
                "national GDP (OECD/EU coverage only). US states: in-state county GDP "
                "(place of work) over the metro's CSA footprint, population netted by "
                "residence. Places left with little residual (e.g. New Jersey) are hidden.",
        "places": places,
    }


if __name__ == "__main__":
    export_jst_returns()
    export_subnational_gdp()
