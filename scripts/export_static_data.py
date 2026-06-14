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


def _i(v):
    """Round to int, or None for missing."""
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else round(float(v))


def _entity_row(r) -> dict:
    """One per-year entity row for the widget, with per-field estimated flags.
    Flag keys mirror model.basis_estimated so subnationalGdpModel.js stays a 1:1 port.
    Null values and false (0) flags are omitted to keep the JSON small — the JS model
    treats a missing field as absent/false."""
    row = {
        "id": r.entity_id, "name": r.name, "kind": r.kind,
        "parent": r.parent, "region": r.region, "year": int(r.year),
    }
    vals = {
        "gdp_nominal_usd": _i(r.gdp_nominal_usd),
        "gdp_ppp_usd": _i(r.gdp_ppp_usd),
        "population": _i(r.population),
        "median_income_ppp_usd": _i(getattr(r, "median_income_ppp_usd", None)),
        "rural_median_ppp_usd": _i(getattr(r, "rural_median_ppp_usd", None)),
    }
    for k, v in vals.items():
        if v is not None:
            row[k] = v
    mi_year = getattr(r, "median_income_year", None)
    if mi_year is not None and not pd.isna(mi_year):
        row["median_income_year"] = int(mi_year)
    # estimated flags — emit only the truthy ones (== 1).
    for flag in ("gdp_nominal_usd_estimated", "gdp_ppp_usd_estimated", "population_estimated",
                 "median_income_estimated", "rural_median_estimated"):
        if bool(getattr(r, flag, False)):
            row[flag] = 1
    return row


def export_subnational_gdp() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.subnational_gdp import estimate

    snapshot = pd.read_parquet(ROOT / "data" / "processed" / "subnational_gdp.parquet")
    snapshot = snapshot.sort_values("gdp_nominal_usd", ascending=False)

    ts = estimate.load_timeseries()
    median_df = None
    med_path = ROOT / "data" / "processed" / "median_income.parquet"
    if med_path.exists():
        median_df = pd.read_parquet(med_path)
    lo, hi = estimate.available_years(ts)

    by_year: dict[str, list[dict]] = {}
    for year in range(lo, hi + 1):
        edf = estimate.entities_for_year(ts, year, median_df)
        # keep only places with something to show on at least one basis
        keep = edf[["gdp_nominal_usd", "gdp_ppp_usd", "population",
                    "median_income_ppp_usd"]].notna().any(axis=1)
        edf = edf[keep]
        by_year[str(year)] = [_entity_row(r) for r in edf.itertuples()]

    payload = {
        "dataset": "subnational_gdp",
        "sources": (
            "BEA Regional (US state GDP; population derived from personal income / "
            "per-capita personal income; public domain) + World Bank WDI (country "
            "GDP, GDP PPP, population; CC BY 4.0) + IMF DataMapper/WEO (near-term "
            "growth for casting the latest actual to the chosen year)."
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
            "median_income": {
                "label": "Median income (PPP)",
                "blurb": "Median disposable income — what a typical household lives "
                         "on, not output per head. GDP/capita is extraction-skewed "
                         "(Norway, North Dakota); this is not.",
            },
        },
        "years": {"min": lo, "max": hi, "default": hi, "list": list(range(lo, hi + 1))},
        "caveats": [
            "Year alignment: every place is shown at the chosen year. A figure released "
            "later than the year (or interpolated between two releases) is marked with an "
            "asterisk (*) — interpolated between actuals, or carried ≤2 years past the "
            "latest actual using IMF WEO growth. Places with no data within ~2 years of "
            "the chosen year drop out rather than be invented.",
            "Median income (PPP): countries use OECD median equivalised disposable "
            "income ÷ World Bank consumption PPP; US states use Census median household "
            "income scaled to the OECD scale via the US anchor. Carried to other years by "
            "PPP-per-capita growth. Comparable in level but not size-adjusted across "
            "countries; OECD/EU coverage only (most non-OECD have no median here).",
            "US-state PPP uses nominal USD as a proxy (US ≈ PPP reference economy; "
            "US PPP/nominal ≈ 1.01).",
            "State population is derived (personal income ÷ per-capita personal income).",
            "DC is excluded from the per-capita ranking: its GDP-per-capita is a "
            "commuter artifact (metro-wide output divided by DC residents only).",
            "Metro punch-out (hinterland) uses the latest-vintage snapshot, not the "
            "year slider.",
        ],
        # default-year entities kept as `entities` for the matcher's state list and any
        # consumer that ignores the slider.
        "entities": by_year[str(hi)],
        "by_year": by_year,
    }
    payload["hinterland"] = _build_hinterland(snapshot)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "subnational_gdp.json"
    out.write_text(json.dumps(payload, separators=(",", ":")))
    size_mb = out.stat().st_size / 1e6
    nh = len(payload["hinterland"]["places"]) if payload["hinterland"] else 0
    print(f"wrote {len(by_year)} years × ~{len(payload['entities'])} entities "
          f"+ {nh} hinterland places -> {out.relative_to(ROOT)} ({size_mb:.2f} MB)")


def _round_place(p: dict) -> dict:
    """JSON-serialise a model place dict (round floats, keep keys the JS expects)."""
    return {
        "id": p["id"], "name": p["name"], "kind": p["kind"], "region": p["region"],
        "curated": bool(p.get("curated", False)),
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
    if (proc / "nonoecd_metros.parquet").exists():
        places += model.nonoecd_places(pd.read_parquet(proc / "nonoecd_metros.parquet"), entities_df)

    places = [_round_place(p) for p in places]
    places.sort(key=lambda p: p["nat_gdp_ppp_usd"], reverse=True)
    return {
        "source": "OECD Functional Urban Areas (countries) + Census/OMB CSA + BEA county "
                  "GDP/population (US states) + curated metros for big non-OECD economies. "
                  "National totals: World Bank WDI / BEA.",
        "note": "Each place's capital and/or largest metro can be removed and values "
                "recomputed on the remaining hinterland. Countries: OECD FUA share of "
                "national GDP. US states: in-state county GDP (place of work) over the "
                "metro's CSA footprint, population netted by residence. Non-OECD "
                "countries (China, India, Brazil, Russia…) use curated metro estimates "
                "(marked ‘est.’). Places left with little residual (e.g. New Jersey) are hidden.",
        "places": places,
    }


def export_negative_productivity() -> None:
    """Localized-inflation lens (ticket 0010): precompute the dispersion series,
    per-month category breakdown, and latest snapshot from the tidy CPI table."""
    import sys

    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.negative_productivity import data as npd
    from app.services.negative_productivity import model

    df = pd.read_parquet(ROOT / "data" / "processed" / "cpi_major_groups.parquet")
    series = model.dispersion_series(df)
    breakdown = model.category_breakdown(df)
    latest = model.latest_snapshot(df)

    payload = {
        "dataset": "cpi_major_groups",
        "lens": "localized_inflation",
        "source": (
            "U.S. BLS, CPI-U (U.S. city average, NSA): six major groups with "
            "continuous history since 1967 + All items. Public domain."
        ),
        "headline_label": npd.HEADLINE_LABEL,
        "categories": list(npd.CATEGORIES.values()),
        "definition": (
            "Localized inflation = relative-price dispersion. dispersion is the "
            "cross-sectional std dev of the six groups' 12-month % changes; spread "
            "is hottest − coldest; skew is Pearson moment skewness. Ball & Mankiw "
            "(1995): positive skew (a few categories spiking up) is the fingerprint "
            "of an adverse supply shock and pulls headline inflation up."
        ),
        "episodes": [{"start": s, "end": e, "label": lab} for s, e, lab in model.EPISODES],
        "first": f"{series[0]['year']:04d}-{series[0]['month']:02d}" if series else None,
        "last": latest.get("label"),
        "series": series,
        "by_month": breakdown,
        "latest": latest,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "negative_productivity_inflation.json"
    out.write_text(json.dumps(payload, separators=(",", ":")))
    size_kb = out.stat().st_size / 1e3
    print(f"wrote {len(series)} months × {len(payload['categories'])} groups "
          f"-> {out.relative_to(ROOT)} ({size_kb:.0f} KB)")


def export_negative_productivity_zombies() -> None:
    """Zombie-firm lens (ticket 0010, lens 2): precompute the zombie-share series and
    the latest roster (mature + all) from the SEC fundamentals panel."""
    import sys

    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.negative_productivity import zombie_model as zm

    df = pd.read_parquet(ROOT / "data" / "processed" / "sec_zombie_fundamentals.parquet")
    series = zm.zombie_share_series(df)
    meta = zm.meta_summary(df)

    payload = {
        "dataset": "sec_zombie_fundamentals",
        "lens": "zombie_firms",
        "source": (
            "SEC EDGAR XBRL frames (data.sec.gov), public domain: OperatingIncomeLoss "
            "(EBIT) ÷ InterestExpense, US-listed firms 2009–present."
        ),
        "definition": meta["definition"],
        "first_year": meta["first_year"],
        "last_complete_year": meta["last_complete_year"],
        "series": series,
        "latest_mature": zm.latest_zombies(df, top_n=25, mature_only=True),
        "latest_all": zm.latest_zombies(df, top_n=25, mature_only=False),
        "caveats": [
            "US-listed XBRL universe only (~2009 on); private, foreign and pre-2009 "
            "firms are absent.",
            "Financials and utilities are NOT excluded (no SIC join yet); they distort "
            "interest-coverage, so the level runs higher than BIS estimates — read the "
            "trend, not the absolute.",
            "Firm 'age' is a reporting-age proxy (years in this panel), not "
            "incorporation age; the BIS screen is age ≥ 10.",
            "Delisted zombies leave the panel (survivorship); the most recent year(s) "
            "are marked provisional while filings arrive.",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "negative_productivity_zombies.json"
    out.write_text(json.dumps(payload, separators=(",", ":")))
    size_kb = out.stat().st_size / 1e3
    print(f"wrote {len(series)} years + {len(payload['latest_mature']['firms'])} "
          f"latest zombies -> {out.relative_to(ROOT)} ({size_kb:.0f} KB)")


def export_espp_median_stock() -> None:
    """Snapshot for the ESPP / median-stock widget.

    Ships per-year median-vs-index series + the pooled distribution, plus an ESPP
    verdict swept over discounts 0–30% in 1% steps so the widget's discount slider
    reads precomputed (tested) values rather than recomputing client-side.
    """
    import sys

    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.espp_median_stock import data as espp_data
    from app.services.espp_median_stock import model as espp_model

    panel = espp_data.load_panel()
    by_year = espp_model.by_year(panel)
    discounts = [round(0.01 * i, 2) for i in range(0, 31)]
    curve = espp_model.espp_curve(panel, discounts)
    default = espp_model.summary(panel)

    def _r(v, n=4):
        return None if v is None or pd.isna(v) else round(float(v), n)

    payload = {
        "dataset": "sp500_constituent_returns",
        "source": (
            "Yahoo Finance monthly adjusted close (split + dividend adjusted = total "
            "return); benchmark = SPY (total-return S&P 500). Universe = current S&P "
            "500 members from the GitHub datasets/s-and-p-500-companies list."
        ),
        "definition": (
            "For each calendar year, the median single-stock one-year total return "
            "(Dec→Dec, dividends reinvested) among S&P 500 members, vs the index "
            "(SPY). ESPP return on your cash = (1 + stock_return) / (1 − discount) − 1."
        ),
        "first_year": int(by_year["year"].min()),
        "last_year": int(by_year["year"].max()),
        "default_discount": espp_model.DEFAULT_DISCOUNT,
        "verdict": default["verdict"],
        "by_year": [
            {
                "year": int(r.year),
                "n": int(r.n_stocks),
                "median_stock": _r(r.median_stock),
                "mean_stock": _r(r.mean_stock),
                "index": _r(r.index_return),
                "p10": _r(r.p10),
                "p25": _r(r.p25),
                "p75": _r(r.p75),
                "p90": _r(r.p90),
                "pct_beat_index": _r(r.pct_beat_index),
                "pct_negative": _r(r.pct_negative),
            }
            for r in by_year.itertuples()
        ],
        # one pooled-distribution snapshot per discount (the slider snaps to 1%)
        "by_discount": {
            f"{int(round(d * 100))}": {
                k: _r(v)
                for k, v in espp_model.pooled_distribution(panel, discount=d).items()
                if isinstance(v, (int, float))
            }
            for d in discounts
        },
        "curve": [
            {
                "discount": _r(r.discount, 2),
                "espp_head_start": _r(r.espp_head_start),
                "espp_median_return": _r(r.espp_median_return),
                "espp_pct_beat_index": _r(r.espp_pct_beat_index),
                "espp_pct_underwater": _r(r.espp_pct_underwater),
            }
            for r in curve.itertuples()
        ],
        "caveats": [
            "Survivorship bias: the universe is TODAY'S S&P 500 members, so dropped, "
            "acquired and bankrupt names are absent and a stock only contributes in "
            "years it was already public. Survivors skew up, so the true median stock "
            "did worse and the left tail is fatter — read 'the median roughly matches "
            "the index over one year' as a survivor-friendly upper bound.",
            "Single year ≠ lifetime: the classic result that most stocks underperform "
            "is a long-horizon, compounding-skew phenomenon. Over one year the median "
            "stock is close to the index; the skew (and the case against holding a "
            "single stock for many years) grows with the horizon.",
            "Median vs mean: the cross-sectional median/mean are effectively equal-"
            "weighted; the index (SPY) is cap-weighted. Part of any gap is weighting, "
            "not just skew. SPY also carries a ~0.09%/yr expense drag vs the raw index.",
            "Returns are Dec→Dec calendar-year total returns; a real ESPP's 12-month "
            "window starts whenever you buy, so treat this as a representative one-year "
            "hold, not a specific purchase date.",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "espp_median_stock.json"
    out.write_text(json.dumps(payload, separators=(",", ":")))
    size_kb = out.stat().st_size / 1e3
    print(f"wrote {len(payload['by_year'])} years + {len(discounts)} discounts "
          f"-> {out.relative_to(ROOT)} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    export_jst_returns()
    export_subnational_gdp()
    export_negative_productivity()
    export_negative_productivity_zombies()
    export_espp_median_stock()
