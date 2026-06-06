"""Data acquisition + compilation for the negative-productivity service (ticket 0010).

First lens — **localized inflation / relative-price dispersion**. The economic idea
(see the conversation behind ticket 0010): a supply shock to one sector shifts
*relative* prices; reallocation frictions keep resources (and the incomes paid to
them) stuck in the now–lower-value activity, so the shock shows up as a widening
*spread* of inflation rates across sectors rather than a uniform rise. Ball &
Mankiw (1995), "Relative-Price Changes as Aggregate Supply Shocks", formalise why
that cross-sectional dispersion (and skew) co-moves with headline inflation.

We track it with the **CPI major groups** (BLS, key `BLS_API_KEY`). Six groups have
continuous monthly history since 1967, so the dispersion series is apples-to-apples
across the 1974, 1979, 2008 and 2021–22 episodes:

    Food and beverages · Housing · Apparel · Transportation · Medical care ·
    Other goods and services

(Recreation and Education & communication were introduced in the 1998 CPI revision;
they are omitted here to keep the panel consistent. "All items" is fetched as the
headline overlay, not as a dispersion category.)

Series are CPI-U, U.S. city average, **not seasonally adjusted** (CUUR…) — we use
12-month changes, which remove seasonality and are the standard for this analysis.

Tidy schema (long), one row per series-month:

    year | month | category | cpi_index

`build()` owns the multi-call flow (the single-URL CLI doesn't fit an API):

    python -m app.services.negative_productivity.data build   # acquire + compile + write
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pandas as pd

from app.core.catalog import PROCESSED_DIR, RAW_DIR
from app.core.datasets import load_processed

DATASET_ID = "cpi_major_groups"
RAW = RAW_DIR / DATASET_ID

BLS_API = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
_UA = {"User-Agent": "vibe-economics/0.1"}

# CPI-U, U.S. city average, NSA. "All items" is the headline; the rest are the
# six major groups with continuous history since 1967. Order = display order.
HEADLINE_ID = "CUUR0000SA0"
CATEGORIES: dict[str, str] = {
    "CUUR0000SAF": "Food and beverages",
    "CUUR0000SAH": "Housing",
    "CUUR0000SAA": "Apparel",
    "CUUR0000SAT": "Transportation",
    "CUUR0000SAM": "Medical care",
    "CUUR0000SAG": "Other goods and services",
}
SERIES: dict[str, str] = {HEADLINE_ID: "All items", **CATEGORIES}

# BLS registered key: <=50 series and <=20 years per request. Windows span 1966
# (one year of lookback so 1967 has a 12-month change) to a generous future bound.
_WINDOWS = [(1966, 1985), (1986, 2005), (2006, 2025), (2026, 2045)]

HEADLINE_LABEL = SERIES[HEADLINE_ID]


# --------------------------------------------------------------------------- #
# Acquire (network) — cache one raw JSON per 20-year window
# --------------------------------------------------------------------------- #
def acquire() -> list[Path]:
    """Fetch the CPI series from BLS in 20-year windows, caching each raw JSON."""
    key = os.environ.get("BLS_API_KEY")
    if not key:
        raise RuntimeError("BLS_API_KEY is not set; needed for CPI data. See ticket 0006.")
    RAW.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with httpx.Client(timeout=90.0) as client:
        for start, end in _WINDOWS:
            dest = RAW / f"cpi_{start}_{end}.json"
            body = {
                "seriesid": list(SERIES),
                "startyear": str(start),
                "endyear": str(end),
                "registrationkey": key,
            }
            resp = client.post(BLS_API, json=body, headers=_UA)
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("status") != "REQUEST_SUCCEEDED":
                raise RuntimeError(f"BLS request failed: {payload.get('message')}")
            dest.write_text(json.dumps(payload))
            paths.append(dest)
    return paths


# --------------------------------------------------------------------------- #
# Compile (raw JSON -> tidy long table)
# --------------------------------------------------------------------------- #
def compile_cpi(raw_dir: str | Path = RAW) -> pd.DataFrame:
    """Read cached BLS window files -> tidy long table (year, month, category, cpi_index)."""
    raw_dir = Path(raw_dir)
    files = sorted(raw_dir.glob("cpi_*.json"))
    if not files:
        raise FileNotFoundError(
            f"No raw CPI files under {raw_dir}. Run: "
            f"python -m app.services.negative_productivity.data build"
        )
    rows: list[dict] = []
    seen: set[tuple] = set()
    for fp in files:
        payload = json.loads(fp.read_text())
        for series in payload.get("Results", {}).get("series", []):
            sid = series["seriesID"]
            name = SERIES.get(sid)
            if name is None:
                continue
            for obs in series.get("data", []):
                period = obs.get("period", "")
                if not period.startswith("M") or period == "M13":  # M13 = annual avg
                    continue
                year = int(obs["year"])
                month = int(period[1:])
                value = obs.get("value")
                if value in (None, "", "-"):
                    continue
                key = (sid, year, month)
                if key in seen:  # windows can't overlap, but guard anyway
                    continue
                seen.add(key)
                rows.append(
                    {"year": year, "month": month, "category": name, "cpi_index": float(value)}
                )
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("Compiled CPI table is empty — check the raw files.")
    return df.sort_values(["category", "year", "month"]).reset_index(drop=True)


def load_cpi() -> pd.DataFrame:
    """Load the compiled tidy CPI table (cached)."""
    return load_processed(DATASET_ID)


# --------------------------------------------------------------------------- #
# Build entrypoint (acquire + compile + write processed parquet)
# --------------------------------------------------------------------------- #
def build() -> Path:
    acquire()
    df = compile_cpi()
    out = PROCESSED_DIR / f"{DATASET_ID}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Built {DATASET_ID}: {len(df)} rows, "
          f"{df['category'].nunique()} series -> {out}")
    return out


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        print(__doc__)
