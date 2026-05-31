"""Median income (PPP) basis for the subnational comparison — ticket 0007.

GDP-per-capita is extraction-skewed (North Dakota, Norway, Alaska all rocket up it).
Median income is a different question: what a *typical* household actually lives on.
This compiles one PPP-comparable median figure per entity:

- **US states:** Census ACS median **household** income (`B19013`), then scaled by the
  US anchor ratio (OECD equivalised median ÷ Census US median) so states sit on the
  same scale as the OECD country figures.
- **Countries:** OECD Income Distribution Database median **equivalised disposable**
  income (national currency), converted to PPP $ with the World Bank private-
  consumption PPP factor (`PA.NUS.PRVT.PP`).

    python -m app.services.subnational_gdp.median_income build

Tidy schema (one row per entity that has a median): ::

    entity_id | median_income_ppp_usd | source | definition | year

Caveats (surfaced in the UI): country medians are equivalised (per consumption unit)
while US states are raw household scaled to match at the US level — comparable in
level, but not adjusted for household-size differences *between* countries. Coverage
is OECD/EU + a few partners; most non-OECD economies have no comparable median here.
"""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

import httpx
import pandas as pd

from app.core import geo
from app.core.catalog import RAW_DIR, get_dataset
from app.core.datasets import load_processed

DATASET_ID = "median_income"
RAW = RAW_DIR / DATASET_ID
_UA = {"User-Agent": "vibe-economics/0.1"}

CENSUS_ACS = "https://api.census.gov/data/2023/acs/acs5"
ACS_MEDIAN_HH = "B19013_001E"  # median household income, last 12 months
OECD_IDD = (
    "https://sdmx.oecd.org/public/rest/data/OECD.WISE.INE,DSD_WISE_IDD@DF_IDD,/"
    ".A.INC_DISP.MEDIAN.XDC_HH_EQ._T.METH2012.D_CUR._Z"
)
WB = "https://api.worldbank.org/v2"
WB_PPP_PRVT = "PA.NUS.PRVT.PP"  # PPP conversion factor, private consumption (LCU/intl$)


# --------------------------------------------------------------------------- #
# Acquire
# --------------------------------------------------------------------------- #
def acquire() -> dict[str, Path]:
    RAW.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("CENSUS_API_KEY")
    paths: dict[str, Path] = {}
    with httpx.Client(follow_redirects=True, timeout=90.0) as client:
        # US states + national median household income (ACS).
        for tag, geo_q in (("states", "state:*"), ("national", "us:1")):
            params = {"get": f"NAME,{ACS_MEDIAN_HH}", "for": geo_q}
            if key:
                params["key"] = key
            r = client.get(CENSUS_ACS, params=params, headers=_UA)
            r.raise_for_status()
            paths[tag] = RAW / f"acs_{tag}.json"
            paths[tag].write_text(r.text)

        # OECD IDD median equivalised disposable income (national currency).
        r = client.get(OECD_IDD, params={"startPeriod": "2017"},
                       headers={**_UA, "Accept": "application/vnd.sdmx.data+csv; labels=id"})
        r.raise_for_status()
        paths["idd"] = RAW / "idd_median.csv"
        paths["idd"].write_text(r.text)

        # World Bank private-consumption PPP conversion factors.
        d = client.get(f"{WB}/country/all/indicator/{WB_PPP_PRVT}",
                       params={"format": "json", "per_page": "20000", "mrv": "6"},
                       headers=_UA)
        d.raise_for_status()
        paths["ppp"] = RAW / "wb_ppp.json"
        paths["ppp"].write_text(d.text)
    return paths


# --------------------------------------------------------------------------- #
# Compile
# --------------------------------------------------------------------------- #
def _acs_rows(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text())
    header, *rows = data
    return [dict(zip(header, r)) for r in rows]


def _wb_latest(path: Path) -> dict[str, float]:
    data = json.loads(Path(path).read_text())
    obs = data[1] if isinstance(data, list) and len(data) > 1 else []
    best: dict[str, tuple[int, float]] = {}
    for o in obs or []:
        v, iso3 = o.get("value"), o.get("countryiso3code")
        if v is None or not iso3:
            continue
        y = int(o["date"])
        if iso3 not in best or y > best[iso3][0]:
            best[iso3] = (y, float(v))
    return {k: v for k, (_, v) in best.items()}


def _idd_latest(path: Path) -> dict[str, tuple[int, float]]:
    """ISO3 -> (year, median equivalised disposable income in national currency)."""
    best: dict[str, tuple[int, float]] = {}
    for r in csv.DictReader(io.StringIO(Path(path).read_text())):
        iso3 = r["REF_AREA"]
        try:
            y, v = int(r["TIME_PERIOD"]), float(r["OBS_VALUE"])
        except (ValueError, KeyError):
            continue
        if iso3 not in best or y > best[iso3][0]:
            best[iso3] = (y, v)
    return best


def compile_median_income(raw_dir: str | Path = RAW) -> pd.DataFrame:
    raw_dir = Path(raw_dir)
    idd = _idd_latest(raw_dir / "idd_median.csv")
    ppp = _wb_latest(raw_dir / "wb_ppp.json")
    ppp["USA"] = 1.0  # US is the PPP numeraire (WB omits it / reports 1)

    rows = []
    # Countries: IDD median (national currency) -> USD PPP via consumption PPP factor.
    us_idd_usd_ppp = None
    for iso3, (year, natcur) in idd.items():
        factor = ppp.get(iso3)
        if not factor:
            continue
        val = natcur / factor
        if iso3 == "USA":
            us_idd_usd_ppp = val
        rows.append({
            "entity_id": iso3, "median_income_ppp_usd": val,
            "source": "OECD IDD median equivalised disposable income / WB consumption PPP",
            "definition": "median equivalised disposable income, PPP $",
            "year": year,
        })

    # US states: Census median household income, anchored to the OECD scale.
    national = _acs_rows(raw_dir / "acs_national.json")
    us_med_hh = float(national[0][ACS_MEDIAN_HH])
    anchor = (us_idd_usd_ppp / us_med_hh) if us_idd_usd_ppp else 1.0
    for r in _acs_rows(raw_dir / "acs_states.json"):
        try:
            med = float(r[ACS_MEDIAN_HH])
        except (ValueError, TypeError):
            continue
        if med <= 0:
            continue
        usps = geo.FIPS_TO_USPS.get(r["state"])
        if not usps:
            continue
        rows.append({
            "entity_id": f"US-{usps}", "median_income_ppp_usd": med * anchor,
            "source": "Census ACS median household income, anchored to OECD equivalised scale",
            "definition": f"median household income (ACS 2023) × {anchor:.3f} US anchor",
            "year": 2023,
        })

    df = pd.DataFrame(rows)
    return df.sort_values("median_income_ppp_usd", ascending=False).reset_index(drop=True)


def load_median_income() -> pd.DataFrame:
    return load_processed(DATASET_ID)


def build() -> Path:
    acquire()
    df = compile_median_income(RAW)
    out = get_dataset(DATASET_ID).processed_path
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    n_c = (~df.entity_id.str.startswith("US-")).sum()
    print(f"Compiled {DATASET_ID}: {len(df)} entities ({n_c} countries + "
          f"{len(df) - n_c} US states) -> {out}")
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        print(__doc__)
