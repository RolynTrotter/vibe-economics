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

# Eurostat median equivalised income, in PPS (PPP-comparable):
#   ilc_di17 = by degree of urbanisation (cities/towns/rural); ilc_di03 = national.
# Used to derive a "rural / outside-the-cities" median per European country.
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
_ES_PARAMS = {"format": "JSON", "statinfo": "MED_EI", "unit": "PPS", "age": "TOTAL", "sex": "T"}

# Eurostat geo code -> ISO3 (mostly ISO2; EL=Greece, UK=United Kingdom, plus EFTA/candidates).
from .metros import PREFIX_TO_ISO3 as _OECD_ISO3  # AT->AUT, EL->GRC, UK->GBR, ...
EUROSTAT_TO_ISO3 = {**_OECD_ISO3, "CY": "CYP", "MT": "MLT", "IS": "ISL",
                    "RS": "SRB", "MK": "MKD"}

# Census ACS B19001 household-income brackets (16) and their upper bounds ($);
# the top bracket ($200k+) is capped at $300k for median interpolation.
ACS_B19001 = [f"B19001_{i:03d}E" for i in range(2, 18)]
_BRACKET_UPPER = [10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 75, 100, 125, 150, 200, 300]
_BRACKET_UPPER = [b * 1000 for b in _BRACKET_UPPER]


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

        # --- "Exclude cities" / rural median income inputs ---
        # Eurostat median income by degree of urbanisation (rural) + national, PPS.
        for tag, code in (("es_urb", "ilc_di17"), ("es_nat", "ilc_di03")):
            r = client.get(f"{EUROSTAT}/{code}",
                           params=[*_ES_PARAMS.items(), ("time", "2022"), ("time", "2023")],
                           headers=_UA)
            r.raise_for_status()
            paths[tag] = RAW / f"{tag}.json"
            paths[tag].write_text(r.text)

        # US: household-income brackets by county (for the nonmetro median) + the
        # CBSA delineation (to classify counties metro vs nonmetro).
        params = {"get": "NAME," + ",".join(["B19001_001E", *ACS_B19001]),
                  "for": "county:*", "in": "state:*"}
        if key:
            params["key"] = key
        r = client.get(CENSUS_ACS, params=params, headers=_UA)
        r.raise_for_status()
        paths["b19001"] = RAW / "acs_county_brackets.json"
        paths["b19001"].write_text(r.text)

        from .us_metros import DELINEATION_URL
        r = client.get(DELINEATION_URL, headers=_UA)
        r.raise_for_status()
        paths["delineation"] = RAW / "list1_2023.xlsx"
        paths["delineation"].write_bytes(r.content)
    return paths


def _jsonstat_latest(path: Path, dims: tuple[str, ...]) -> dict:
    """Parse a Eurostat JSON-stat file -> {dim-tuple: value} keeping the latest year.
    `dims` are the dimensions to key on (e.g. ('geo',) or ('geo','deg_urb'))."""
    d = json.loads(Path(path).read_text())
    ids, sizes, val = d["id"], d["size"], d["value"]
    idx2code = [{i: c for c, i in d["dimension"][k]["category"]["index"].items()} for k in ids]
    tpos = ids.index("time")
    best: dict[tuple, tuple[str, float]] = {}
    for lin_str, v in val.items():
        if v is None:
            continue
        rem, coords = int(lin_str), [0] * len(sizes)
        for j in range(len(sizes) - 1, -1, -1):
            coords[j] = rem % sizes[j]
            rem //= sizes[j]
        rec = {ids[i]: idx2code[i][coords[i]] for i in range(len(ids))}
        key = tuple(rec[dm] for dm in dims)
        year = rec["time"]
        if key not in best or year > best[key][0]:
            best[key] = (year, float(v))
    return {k: v for k, (_, v) in best.items()}


def _bracket_median(counts: list[float]) -> float | None:
    """Interpolated median of the 16 ACS B19001 household-income brackets."""
    total = sum(counts)
    if total <= 0:
        return None
    half, cum, lower = total / 2.0, 0.0, 0.0
    for c, upper in zip(counts, _BRACKET_UPPER):
        if c > 0 and cum + c >= half:
            return lower + (half - cum) / c * (upper - lower)
        cum += c
        lower = upper
    return None


def _metro_county_fips(delineation: Path) -> set[str]:
    """5-digit FIPS of counties in a Metropolitan Statistical Area (vs nonmetro)."""
    d = pd.read_excel(delineation, header=2, dtype=str)
    d = d[d["Metropolitan/Micropolitan Statistical Area"] == "Metropolitan Statistical Area"]
    return set(d["FIPS State Code"] + d["FIPS County Code"])


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
    nat_usd: dict[str, float] = {}
    for iso3, (year, natcur) in idd.items():
        factor = ppp.get(iso3)
        if not factor:
            continue
        val = natcur / factor
        nat_usd[iso3] = val
        if iso3 == "USA":
            us_idd_usd_ppp = val
        rows.append({
            "entity_id": iso3, "median_income_ppp_usd": val, "rural_median_ppp_usd": None,
            "source": "OECD IDD median equivalised disposable income / WB consumption PPP",
            "definition": "median equivalised disposable income, PPP $",
            "year": year,
        })

    # --- European rural median: scale each country's national figure by the
    # Eurostat rural/national ratio (both in PPS, so the ratio is unit-free). ---
    es_nat = _jsonstat_latest(raw_dir / "es_nat.json", ("geo",))           # {geo: median PPS}
    es_urb = _jsonstat_latest(raw_dir / "es_urb.json", ("geo", "deg_urb"))  # {(geo,deg): PPS}
    for row in rows:
        iso3 = row["entity_id"]
        geo2 = next((g for g, i in EUROSTAT_TO_ISO3.items() if i == iso3), None)
        nat_pps = es_nat.get((geo2,)) if geo2 else None
        rural_pps = es_urb.get((geo2, "DEG3")) if geo2 else None
        if nat_pps and rural_pps and iso3 in nat_usd:
            row["rural_median_ppp_usd"] = nat_usd[iso3] * (rural_pps / nat_pps)

    # US states: Census median household income, anchored to the OECD scale.
    national = _acs_rows(raw_dir / "acs_national.json")
    us_med_hh = float(national[0][ACS_MEDIAN_HH])
    anchor = (us_idd_usd_ppp / us_med_hh) if us_idd_usd_ppp else 1.0

    # State nonmetro median: pool the income brackets of all non-metropolitan counties
    # in each state and interpolate the median, then apply the US anchor.
    metro_fips = _metro_county_fips(raw_dir / "list1_2023.xlsx")
    state_nonmetro: dict[str, list[float]] = {}
    for r in _acs_rows(raw_dir / "acs_county_brackets.json"):
        fips = r["state"] + r["county"]
        if fips in metro_fips:
            continue
        acc = state_nonmetro.setdefault(r["state"], [0.0] * len(ACS_B19001))
        for i, var in enumerate(ACS_B19001):
            try:
                acc[i] += float(r[var])
            except (ValueError, TypeError):
                pass
    # Require a non-trivial nonmetro population (>= 20k households) so a state's rural
    # median isn't one tiny affluent county.
    nonmetro_median = {s: _bracket_median(c) for s, c in state_nonmetro.items()
                       if sum(c) >= 20_000}

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
        nm = nonmetro_median.get(r["state"])
        rows.append({
            "entity_id": f"US-{usps}", "median_income_ppp_usd": med * anchor,
            "rural_median_ppp_usd": (nm * anchor) if nm else None,
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
