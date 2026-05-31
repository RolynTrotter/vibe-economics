"""Multi-year time-series acquisition + compilation for the subnational-GDP service
(ticket 0009 — year slider + same-year smoothing/imputation).

The original service (ticket 0002) stores **one row per place at its latest year**.
That's fine for a single snapshot, but it can't answer "put every place on the same
year" because sources lag differently (BEA states reach 2025; World Bank countries
often stop at 2024; some at 2023). To align everything to one chosen year we need
the underlying *history* of each metric, plus a near-term growth signal to cast the
laggards forward.

This module owns that history. It writes a **long, tidy** table:

    entity_id | name | kind | parent | region | year | metric | value | source

- ``metric``  one of ``gdp_nominal_usd`` | ``gdp_ppp_usd`` | ``population`` (absolute units).
- ``source``  ``bea`` | ``worldbank`` (observed *actuals* — establish the data frontier)
              or ``imf`` (IMF WEO; observations + near-term forecasts, used only to
              *extrapolate* an actual forward — never spliced as a level; see estimate.py).

Sources
-------
- **BEA Regional** (key, ``BEA_API_KEY``) — US state GDP (SAGDP2, current dollars,
  1997–latest incl. a preliminary current year) + personal income / per-capita income
  (to derive state population per year). US Government work, public domain.
- **World Bank WDI** (key-free, CC BY 4.0) — country GDP (current US$), GDP PPP
  (current international $), population, full history.
- **IMF DataMapper / WEO** (key-free) — NGDPD (GDP, US$ bn), PPPGDP (GDP PPP, intl$ bn),
  LP (population, millions). Covers the current/forecast years the World Bank still
  lags on, so we can grow a country's last *observed* figure to the target year.

Build (acquire + compile + write parquet)::

    python -m app.services.subnational_gdp.timeseries build

``acquire()`` caches each raw response under ``data/raw/subnational_gdp_timeseries/``
so re-compiles never re-hit the network.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pandas as pd

from app.core import geo
from app.core.catalog import RAW_DIR, get_dataset
from app.core.datasets import load_processed

DATASET_ID = "subnational_gdp_timeseries"
RAW = RAW_DIR / DATASET_ID

# Earliest year we keep. BEA state current-dollar GDP (SAGDP2) starts in 1997, so the
# states+countries ladder is only complete from 1997 on; we fetch a touch earlier so
# interpolation near the start has context.
START_YEAR = 1995

# World Bank indicator codes.
WB_GDP_NOMINAL = "NY.GDP.MKTP.CD"      # GDP, current US$
WB_GDP_PPP = "NY.GDP.MKTP.PP.CD"       # GDP, PPP (current international $)
WB_POP = "SP.POP.TOTL"                 # Population, total

# IMF DataMapper (WEO) indicator codes -> our metric. Units: NGDPD/PPPGDP in billions,
# LP in millions; scaled to absolute units on compile.
IMF_INDICATORS = {
    "NGDPD": ("gdp_nominal_usd", 1e9),
    "PPPGDP": ("gdp_ppp_usd", 1e9),
    "LP": ("population", 1e6),
}

# BEA Regional tables / line codes (mirror data.py).
BEA_GDP_TABLE = "SAGDP2"               # GDP by state (current dollars), 1997+
BEA_GDP_LINE = "1"                     # All industry total
BEA_SUMMARY_TABLE = "SASUMMARY"
BEA_PI_LINE = "5"                      # Personal income ($ millions, UNIT_MULT=6)
BEA_PCPI_LINE = "10"                   # Per capita personal income ($/person)

_UA = {"User-Agent": "vibe-economics/0.1"}
# IMF's edge/WAF rejects our default and browser UAs (403) but serves a curl-style
# one, so the IMF calls override the header.
_IMF_HEADERS = {"User-Agent": "curl/8.0", "Accept": "application/json"}


# --------------------------------------------------------------------------- #
# Acquire (network)
# --------------------------------------------------------------------------- #
def _get_json(client: httpx.Client, url: str, params: dict | None = None,
              headers: dict | None = None) -> dict:
    resp = client.get(url, params=params or {}, headers=headers or _UA)
    resp.raise_for_status()
    return resp.json()


def acquire() -> dict[str, Path]:
    """Fetch BEA + World Bank (full history) + IMF WEO, caching each as raw JSON."""
    bea_key = os.environ.get("BEA_API_KEY")
    if not bea_key:
        raise RuntimeError("BEA_API_KEY is not set; needed for US state GDP.")
    RAW.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        bea_url = "https://apps.bea.gov/api/data/"
        # BEA: state GDP (current dollars), all states, all years.
        gdp = _get_json(client, bea_url, {
            "UserID": bea_key, "method": "GetData", "datasetname": "Regional",
            "TableName": BEA_GDP_TABLE, "LineCode": BEA_GDP_LINE,
            "GeoFips": "STATE", "Year": "ALL", "ResultFormat": "JSON",
        })
        paths["bea_gdp"] = RAW / "bea_gdp.json"
        paths["bea_gdp"].write_text(json.dumps(gdp))
        # BEA: personal income + per-capita income (to derive population per year).
        for line, tag in ((BEA_PI_LINE, "bea_pi"), (BEA_PCPI_LINE, "bea_pcpi")):
            d = _get_json(client, bea_url, {
                "UserID": bea_key, "method": "GetData", "datasetname": "Regional",
                "TableName": BEA_SUMMARY_TABLE, "LineCode": line,
                "GeoFips": "STATE", "Year": "ALL", "ResultFormat": "JSON",
            })
            paths[tag] = RAW / f"{tag}.json"
            paths[tag].write_text(json.dumps(d))

        # World Bank: country list (to drop aggregates) + 3 indicators, full history.
        wb = "https://api.worldbank.org/v2"
        countries = _get_json(client, f"{wb}/country", {"format": "json", "per_page": "400"})
        paths["wb_countries"] = RAW / "wb_countries.json"
        paths["wb_countries"].write_text(json.dumps(countries))
        for ind, tag in ((WB_GDP_NOMINAL, "wb_gdp"), (WB_GDP_PPP, "wb_gdp_ppp"),
                         (WB_POP, "wb_pop")):
            d = _get_json(client, f"{wb}/country/all/indicator/{ind}",
                          {"format": "json", "per_page": "20000",
                           "date": f"{START_YEAR}:2025"})
            paths[tag] = RAW / f"{tag}.json"
            paths[tag].write_text(json.dumps(d))

        # IMF DataMapper (WEO): each indicator returns every economy, all years +
        # forecasts, in one call.
        for ind in IMF_INDICATORS:
            d = _get_json(client, f"https://www.imf.org/external/datamapper/api/v1/{ind}",
                          headers=_IMF_HEADERS)
            paths[f"imf_{ind}"] = RAW / f"imf_{ind}.json"
            paths[f"imf_{ind}"].write_text(json.dumps(d))

    return paths


# --------------------------------------------------------------------------- #
# Compile (pure, reads cached raw) — long tidy table
# --------------------------------------------------------------------------- #
def _bea_rows(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text())
    return data["BEAAPI"]["Results"]["Data"]


def _bea_value(cell: str | None) -> float | None:
    if cell is None or "(" in cell:
        return None
    try:
        return float(cell.replace(",", ""))
    except ValueError:
        return None


def _bea_series_by_state(rows: list[dict]) -> dict[str, dict[int, float]]:
    """USPS -> {year: value} for every state row with a real value."""
    out: dict[str, dict[int, float]] = {}
    for r in rows:
        ent = geo.fips_to_state_entity(r.get("GeoFips", ""))
        if ent is None:
            continue
        val = _bea_value(r.get("DataValue"))
        if val is None:
            continue
        usps = ent.id.split("-", 1)[1]
        out.setdefault(usps, {})[int(r["TimePeriod"])] = val
    return out


def _compile_states(raw_dir: Path) -> pd.DataFrame:
    gdp = _bea_series_by_state(_bea_rows(raw_dir / "bea_gdp.json"))     # $ millions
    pi = _bea_series_by_state(_bea_rows(raw_dir / "bea_pi.json"))       # $ millions
    pcpi = _bea_series_by_state(_bea_rows(raw_dir / "bea_pcpi.json"))   # $/person

    rows = []
    for usps, years in gdp.items():
        ent = geo.state_entity(usps)
        base = {"entity_id": ent.id, "name": ent.name, "kind": ent.kind,
                "parent": ent.parent, "region": "United States", "source": "bea"}
        for year, gdp_millions in years.items():
            gdp_usd = gdp_millions * 1e6
            rows.append({**base, "year": year, "metric": "gdp_nominal_usd", "value": gdp_usd})
            # US states: PPP ≈ nominal (US ≈ PPP reference economy; see data.py).
            rows.append({**base, "year": year, "metric": "gdp_ppp_usd", "value": gdp_usd})
        # Population per year = personal income ($) / per-capita income ($/person).
        for year, pi_millions in pi.get(usps, {}).items():
            pc = pcpi.get(usps, {}).get(year)
            if pc:
                rows.append({**base, "year": year, "metric": "population",
                             "value": pi_millions * 1e6 / pc})
    return pd.DataFrame(rows)


def _wb_series(path: Path) -> dict[str, dict[int, float]]:
    """ISO3 -> {year: value} for every non-null World Bank observation."""
    data = json.loads(Path(path).read_text())
    obs = data[1] if isinstance(data, list) and len(data) > 1 else []
    out: dict[str, dict[int, float]] = {}
    for o in obs or []:
        val = o.get("value")
        iso3 = o.get("countryiso3code")
        if val is None or not iso3:
            continue
        out.setdefault(iso3, {})[int(o["date"])] = float(val)
    return out


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


def _imf_series(path: Path) -> dict[str, dict[int, float]]:
    """ISO3 -> {year: value} from an IMF DataMapper indicator payload."""
    data = json.loads(Path(path).read_text())
    values = (data.get("values") or {})
    # payload shape: {"values": {"<IND>": {"<ISO3>": {"<year>": value, ...}}}}
    inner = next(iter(values.values()), {}) if values else {}
    out: dict[str, dict[int, float]] = {}
    for iso3, by_year in inner.items():
        if len(iso3) != 3:
            continue
        clean = {}
        for y, v in by_year.items():
            if v is None:
                continue
            try:
                clean[int(y)] = float(v)
            except (TypeError, ValueError):
                continue
        if clean:
            out[iso3.upper()] = clean
    return out


def _compile_countries(raw_dir: Path) -> pd.DataFrame:
    names = _real_country_iso3s(raw_dir / "wb_countries.json")
    wb = {
        "gdp_nominal_usd": _wb_series(raw_dir / "wb_gdp.json"),
        "gdp_ppp_usd": _wb_series(raw_dir / "wb_gdp_ppp.json"),
        "population": _wb_series(raw_dir / "wb_pop.json"),
    }
    imf = {}
    for ind, (metric, scale) in IMF_INDICATORS.items():
        p = raw_dir / f"imf_{ind}.json"
        if p.exists():
            imf[metric] = {iso3: {y: v * scale for y, v in s.items()}
                           for iso3, s in _imf_series(p).items()}

    rows = []
    for iso3, meta in names.items():
        ent = geo.country_entity(iso3, meta["name"])
        base = {"entity_id": ent.id, "name": ent.name, "kind": ent.kind,
                "parent": ent.parent, "region": meta["region"]}
        for metric, series in wb.items():
            for year, val in series.get(iso3, {}).items():
                rows.append({**base, "year": year, "metric": metric,
                             "value": val, "source": "worldbank"})
        for metric, series in imf.items():
            for year, val in series.get(iso3, {}).items():
                if year < START_YEAR:
                    continue
                rows.append({**base, "year": year, "metric": metric,
                             "value": val, "source": "imf"})
    return pd.DataFrame(rows)


def compile_timeseries(raw_dir: str | Path = RAW) -> pd.DataFrame:
    """Compile cached BEA + World Bank + IMF raw JSON into the long tidy series."""
    raw_dir = Path(raw_dir)
    out = pd.concat([_compile_states(raw_dir), _compile_countries(raw_dir)],
                    ignore_index=True)
    out = out[out["value"] > 0].reset_index(drop=True)
    out["year"] = out["year"].astype(int)
    return out.sort_values(["entity_id", "metric", "source", "year"]).reset_index(drop=True)


def load_timeseries() -> pd.DataFrame:
    """Load the compiled long time-series table."""
    return load_processed(DATASET_ID)


def build() -> Path:
    """Acquire + compile + write the processed parquet. Returns the output path."""
    acquire()
    df = compile_timeseries(RAW)
    out = get_dataset(DATASET_ID).processed_path
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    n_ent = df["entity_id"].nunique()
    print(f"Compiled {DATASET_ID}: {len(df)} rows, {n_ent} entities, "
          f"years {df.year.min()}-{df.year.max()} -> {out}")
    return out


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        print(__doc__)
