"""Data acquisition + compilation for the subnational-GDP service (ticket 0002).

Unlike the safe-withdrawal reference service (one file from one URL), this dataset
is stitched from two authoritative APIs:

- **BEA Regional** (free key, `BEA_API_KEY`) — US state GDP (current dollars) and
  the pieces to derive state population. License: US Government work, public domain.
- **World Bank WDI** (key-free, CC BY 4.0) — country GDP (current US$), GDP PPP
  (current international $), and population.

Because acquisition needs several API calls, the CLI's single-URL `acquire` doesn't
fit. Instead this module owns the flow:

    python -m app.services.subnational_gdp.data build   # acquire + compile + write parquet

`acquire()` caches each raw API response under ``data/raw/subnational_gdp/`` so
re-compiles never re-hit the network. `compile_subnational_gdp()` reads those raw
files and emits the tidy table the model/router consume.

Tidy schema (one row per place, absolute units):

    entity_id | name | kind | parent | gdp_nominal_usd | gdp_ppp_usd | population | year

- ``gdp_nominal_usd``  GDP at current market exchange rates, USD.
- ``gdp_ppp_usd``      GDP at PPP, current international $. For **US states** BEA only
                       publishes nominal USD; we set ppp = nominal because the US is
                       (essentially) the PPP reference economy — US PPP/nominal ≈ 1.01
                       (World Bank). Surfaced as a caveat in the UI. Countries use the
                       real World Bank PPP figure.
- ``population``       Mid-year population.
- ``year``             Year of the GDP figure (per entity; sources lag differently).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pandas as pd

from app.core import geo
from app.core.catalog import RAW_DIR
from app.core.datasets import load_processed

DATASET_ID = "subnational_gdp"
RAW = RAW_DIR / DATASET_ID

# World Bank indicator codes.
WB_GDP_NOMINAL = "NY.GDP.MKTP.CD"      # GDP, current US$
WB_GDP_PPP = "NY.GDP.MKTP.PP.CD"       # GDP, PPP (current international $)
WB_POP = "SP.POP.TOTL"                 # Population, total

# BEA Regional tables / line codes.
BEA_GDP_TABLE = "SAGDP2"               # GDP by state (current dollars)
BEA_GDP_LINE = "1"                     # All industry total
BEA_SUMMARY_TABLE = "SASUMMARY"        # has personal income (5) + per-cap income (10)
BEA_PI_LINE = "5"                      # Personal income ($ thousands)
BEA_PCPI_LINE = "10"                   # Per capita personal income ($)

_UA = {"User-Agent": "vibe-economics/0.1"}


# --------------------------------------------------------------------------- #
# Acquire (network) — cache raw responses under data/raw/subnational_gdp/
# --------------------------------------------------------------------------- #
def _get_json(client: httpx.Client, url: str, params: dict) -> dict:
    resp = client.get(url, params=params, headers=_UA)
    resp.raise_for_status()
    return resp.json()


def acquire() -> dict[str, Path]:
    """Fetch BEA + World Bank responses, caching each as raw JSON. Returns paths."""
    bea_key = os.environ.get("BEA_API_KEY")
    if not bea_key:
        raise RuntimeError(
            "BEA_API_KEY is not set; needed for US state GDP. See ticket 0006."
        )
    RAW.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    with httpx.Client(follow_redirects=True, timeout=90.0) as client:
        # --- BEA: state GDP (current dollars), all states, all available years ---
        bea_url = "https://apps.bea.gov/api/data/"
        gdp = _get_json(client, bea_url, {
            "UserID": bea_key, "method": "GetData", "datasetname": "Regional",
            "TableName": BEA_GDP_TABLE, "LineCode": BEA_GDP_LINE,
            "GeoFips": "STATE", "Year": "ALL", "ResultFormat": "JSON",
        })
        paths["bea_gdp"] = RAW / "bea_gdp.json"
        paths["bea_gdp"].write_text(json.dumps(gdp))

        # --- BEA: personal income + per-capita income (to derive population) ---
        for line, tag in ((BEA_PI_LINE, "bea_pi"), (BEA_PCPI_LINE, "bea_pcpi")):
            d = _get_json(client, bea_url, {
                "UserID": bea_key, "method": "GetData", "datasetname": "Regional",
                "TableName": BEA_SUMMARY_TABLE, "LineCode": line,
                "GeoFips": "STATE", "Year": "ALL", "ResultFormat": "JSON",
            })
            paths[tag] = RAW / f"{tag}.json"
            paths[tag].write_text(json.dumps(d))

        # --- World Bank: country list (to drop aggregates) + 3 indicators ---
        wb = "https://api.worldbank.org/v2"
        countries = _get_json(client, f"{wb}/country", {"format": "json", "per_page": "400"})
        paths["wb_countries"] = RAW / "wb_countries.json"
        paths["wb_countries"].write_text(json.dumps(countries))

        for ind, tag in ((WB_GDP_NOMINAL, "wb_gdp"), (WB_GDP_PPP, "wb_gdp_ppp"),
                         (WB_POP, "wb_pop")):
            d = _get_json(client, f"{wb}/country/all/indicator/{ind}",
                          {"format": "json", "per_page": "20000", "mrv": "6"})
            paths[tag] = RAW / f"{tag}.json"
            paths[tag].write_text(json.dumps(d))

    return paths


# --------------------------------------------------------------------------- #
# Compile (pure, reads cached raw) — tidy table
# --------------------------------------------------------------------------- #
def _bea_rows(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text())
    return data["BEAAPI"]["Results"]["Data"]


def _bea_value(cell: str) -> float | None:
    """BEA DataValue is a string with thousands commas; '(NA)' / '(D)' = missing."""
    if cell is None or "(" in cell:
        return None
    try:
        return float(cell.replace(",", ""))
    except ValueError:
        return None


def _latest_by_state(rows: list[dict]) -> dict[str, tuple[int, float]]:
    """USPS -> (year, value) for the most recent year a state has a real value."""
    best: dict[str, tuple[int, float]] = {}
    for r in rows:
        ent = geo.fips_to_state_entity(r.get("GeoFips", ""))
        if ent is None:
            continue
        val = _bea_value(r.get("DataValue"))
        if val is None:
            continue
        year = int(r["TimePeriod"])
        usps = ent.id.split("-", 1)[1]
        if usps not in best or year > best[usps][0]:
            best[usps] = (year, val)
    return best


def _compile_states(raw_dir: Path) -> pd.DataFrame:
    gdp = _latest_by_state(_bea_rows(raw_dir / "bea_gdp.json"))          # $ millions
    pi = _latest_by_state(_bea_rows(raw_dir / "bea_pi.json"))            # $ thousands
    pcpi = _latest_by_state(_bea_rows(raw_dir / "bea_pcpi.json"))        # $ per person

    rows = []
    for usps, (year, gdp_millions) in gdp.items():
        ent = geo.state_entity(usps)
        gdp_usd = gdp_millions * 1e6
        population = None
        if usps in pi and usps in pcpi and pcpi[usps][1]:
            # personal income ($ millions, BEA UNIT_MULT=6) / per-capita income
            # ($/person) = people
            population = pi[usps][1] * 1e6 / pcpi[usps][1]
        rows.append({
            "entity_id": ent.id, "name": ent.name, "kind": ent.kind,
            "parent": ent.parent, "region": "United States",
            "gdp_nominal_usd": gdp_usd,
            "gdp_ppp_usd": gdp_usd,  # US ≈ PPP base; see module docstring + UI caveat
            "population": population, "year": year,
        })
    return pd.DataFrame(rows)


def _wb_latest(path: Path) -> dict[str, tuple[int, float]]:
    """ISO3 -> (year, value) for the most recent non-null World Bank observation."""
    data = json.loads(Path(path).read_text())
    obs = data[1] if isinstance(data, list) and len(data) > 1 else []
    best: dict[str, tuple[int, float]] = {}
    for o in obs or []:
        val = o.get("value")
        iso3 = o.get("countryiso3code")
        if val is None or not iso3:
            continue
        year = int(o["date"])
        if iso3 not in best or year > best[iso3][0]:
            best[iso3] = (year, float(val))
    return best


def _real_country_iso3s(path: Path) -> dict[str, dict]:
    """ISO3 -> {name, region} for genuine countries (World Bank aggregates dropped)."""
    data = json.loads(Path(path).read_text())
    out: dict[str, dict] = {}
    for c in data[1] if isinstance(data, list) and len(data) > 1 else []:
        region = (c.get("region") or {}).get("value", "")
        iso3 = c.get("id", "")
        if region and region != "Aggregates" and len(iso3) == 3:
            out[iso3] = {"name": c.get("name", iso3), "region": region}
    return out


def _compile_countries(raw_dir: Path) -> pd.DataFrame:
    names = _real_country_iso3s(raw_dir / "wb_countries.json")
    gdp = _wb_latest(raw_dir / "wb_gdp.json")
    gdp_ppp = _wb_latest(raw_dir / "wb_gdp_ppp.json")
    pop = _wb_latest(raw_dir / "wb_pop.json")

    rows = []
    for iso3, meta in names.items():
        if iso3 not in gdp:
            continue
        year, gdp_usd = gdp[iso3]
        ent = geo.country_entity(iso3, meta["name"])
        rows.append({
            "entity_id": ent.id, "name": ent.name, "kind": ent.kind,
            "parent": ent.parent, "region": meta["region"],
            "gdp_nominal_usd": gdp_usd,
            "gdp_ppp_usd": gdp_ppp.get(iso3, (None, None))[1],
            "population": pop.get(iso3, (None, None))[1], "year": year,
        })
    return pd.DataFrame(rows)


def compile_subnational_gdp(raw_dir: str | Path = RAW) -> pd.DataFrame:
    """Compile cached BEA + World Bank raw JSON into the tidy comparison table."""
    raw_dir = Path(raw_dir)
    states = _compile_states(raw_dir)
    countries = _compile_countries(raw_dir)
    out = pd.concat([states, countries], ignore_index=True)
    out = out[out["gdp_nominal_usd"] > 0].reset_index(drop=True)
    return out.sort_values("gdp_nominal_usd", ascending=False).reset_index(drop=True)


def load_entities() -> pd.DataFrame:
    """Load the compiled comparison table, with the median-income column merged in
    (left join) when that dataset has been built — so the `median_income` basis works."""
    df = load_processed(DATASET_ID)
    try:
        from .median_income import load_median_income
        med = load_median_income()[["entity_id", "median_income_ppp_usd"]]
        df = df.merge(med, on="entity_id", how="left")
    except (FileNotFoundError, KeyError):
        df["median_income_ppp_usd"] = float("nan")
    return df


def build() -> Path:
    """Acquire + compile + write the processed parquet. Returns the output path."""
    from app.core.catalog import get_dataset

    acquire()
    df = compile_subnational_gdp(RAW)
    out = get_dataset(DATASET_ID).processed_path
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Compiled {DATASET_ID}: {len(df)} entities -> {out}")
    return out


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        print(__doc__)
