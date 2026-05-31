"""US metros for the per-state punch-out (ticket 0008, phase 2).

Phase 1 removes whole metros from whole countries using OECD FUA shares. Phase 2
removes each **US state's** metro(s) from that state — and the hard part is that US
metros cross state lines (NYC = NY+NJ+CT, Washington = DC+VA+MD+WV). OECD doesn't
expose US FUA→county membership, so we build the footprint from US data:

- **Footprint = Combined Statistical Area (CSA), falling back to CBSA** when a metro
  has no CSA. The CSA is the broad commuting-zone definition — the NY CSA pulls in
  the Hudson Valley (Poughkeepsie, Newburgh), Bridgeport, etc. — so it approximates
  the breadth of OECD's FUAs and we strip a comparably-sized metro on the US side.
- **Split across states by county**, using **BEA county GDP** (CAGDP2, *place of
  work*) and **BEA county population** (CAINC1, *residence*). Removing a metro's
  in-state counties from a state nets commuters out correctly: a NJ→Manhattan
  commuter's home county leaves NJ's population while their work county leaves NY's
  GDP. (See docs/tickets/0008-metro-allocation-analysis.md.)

    python -m app.services.subnational_gdp.us_metros build

Tidy schema (one row per state × metro it touches):

    state_usps | state_name | metro_id | metro_name | metro_level (CSA|CBSA)
              | in_state_gdp | in_state_pop | county_count | has_state_capital | year
"""
from __future__ import annotations

from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from app.core import geo
from app.core.catalog import RAW_DIR, get_dataset
from app.core.datasets import load_processed

DATASET_ID = "us_state_metros"
RAW = RAW_DIR / DATASET_ID

DELINEATION_URL = (
    "https://www2.census.gov/programs-surveys/metro-micro/geographies/"
    "reference-files/2023/delineation-files/list1_2023.xlsx"
)
_UA = {"User-Agent": "vibe-economics/0.1"}

# State capital -> 5-digit county/equivalent FIPS, to flag each state's "capital
# metro" (the metro whose counties contain the capital). Independent-city capitals
# (VA) use their city FIPS, which BEA reports.
CAPITAL_COUNTY_FIPS: dict[str, str] = {
    "AL": "01101", "AK": "02110", "AZ": "04013", "AR": "05119", "CA": "06067",
    "CO": "08031", "CT": "09003", "DE": "10001", "FL": "12073", "GA": "13121",
    "HI": "15003", "ID": "16001", "IL": "17167", "IN": "18097", "IA": "19153",
    "KS": "20177", "KY": "21073", "LA": "22033", "ME": "23011", "MD": "24003",
    "MA": "25025", "MI": "26065", "MN": "27123", "MS": "28049", "MO": "29051",
    "MT": "30049", "NE": "31109", "NV": "32510", "NH": "33013", "NJ": "34021",
    "NM": "35049", "NY": "36001", "NC": "37183", "ND": "38015", "OH": "39049",
    "OK": "40109", "OR": "41047", "PA": "42043", "RI": "44007", "SC": "45079",
    "SD": "46065", "TN": "47037", "TX": "48453", "UT": "49035", "VT": "50023",
    "VA": "51760", "WA": "53067", "WV": "54039", "WI": "55025", "WY": "56021",
    "DC": "11001",
}


# --------------------------------------------------------------------------- #
# Acquire
# --------------------------------------------------------------------------- #
def _bea_county(client: httpx.Client, table: str, line: str) -> list[dict]:
    import os
    key = os.environ.get("BEA_API_KEY")
    if not key:
        raise RuntimeError("BEA_API_KEY is not set; needed for county GDP/population.")
    r = client.get("https://apps.bea.gov/api/data/", params={
        "UserID": key, "method": "GetData", "datasetname": "Regional",
        "TableName": table, "LineCode": line, "GeoFips": "COUNTY",
        "Year": "LAST5", "ResultFormat": "JSON",
    }, headers=_UA)
    r.raise_for_status()
    return r.json()["BEAAPI"]["Results"]["Data"]


def acquire() -> dict[str, Path]:
    import json
    RAW.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        r = client.get(DELINEATION_URL, headers=_UA)
        r.raise_for_status()
        paths["delineation"] = RAW / "list1_2023.xlsx"
        paths["delineation"].write_bytes(r.content)

        gdp = _bea_county(client, "CAGDP2", "1")      # county GDP, current $
        paths["gdp"] = RAW / "county_gdp.json"
        paths["gdp"].write_text(json.dumps(gdp))

        pop = _bea_county(client, "CAINC1", "2")      # county population
        paths["pop"] = RAW / "county_pop.json"
        paths["pop"].write_text(json.dumps(pop))
    return paths


# --------------------------------------------------------------------------- #
# Compile
# --------------------------------------------------------------------------- #
def _bea_series(path: Path) -> pd.Series:
    """fips5 -> value (latest year), to dollars/persons via UNIT_MULT."""
    import json
    df = pd.DataFrame(json.loads(Path(path).read_text()))
    df["year"] = df["TimePeriod"].astype(int)
    latest = df["year"].max()
    df = df[df["year"] == latest].copy()
    df["fips"] = df["GeoFips"].str[:5]
    df["val"] = (
        pd.to_numeric(df["DataValue"].str.replace(",", ""), errors="coerce")
        * 10 ** df["UNIT_MULT"].astype(int)
    )
    return df.dropna(subset=["val"]).set_index("fips")["val"], latest


def compile_us_metros(raw_dir: str | Path = RAW) -> pd.DataFrame:
    raw_dir = Path(raw_dir)
    gdp, gyear = _bea_series(raw_dir / "county_gdp.json")
    pop, _ = _bea_series(raw_dir / "county_pop.json")

    d = pd.read_excel(raw_dir / "list1_2023.xlsx", header=2, dtype=str)
    d = d[d["Metropolitan/Micropolitan Statistical Area"] == "Metropolitan Statistical Area"].copy()
    d["fips"] = d["FIPS State Code"] + d["FIPS County Code"]
    # CSA-first footprint (broad commuting zone), else CBSA.
    has_csa = d["CSA Code"].notna()
    d["metro_id"] = np.where(has_csa, "C" + d["CSA Code"].fillna(""), "B" + d["CBSA Code"])
    d["metro_name"] = np.where(has_csa, d["CSA Title"], d["CBSA Title"])
    d["metro_level"] = np.where(has_csa, "CSA", "CBSA")
    d["state_usps"] = d["FIPS State Code"].map(
        {f: u for f, u in geo.FIPS_TO_USPS.items()}
    )
    d = d.dropna(subset=["state_usps"])
    d["gdp"] = d["fips"].map(gdp)
    d["pop"] = d["fips"].map(pop)

    # State totals from the SAME county series (so a metro's share is exact and the
    # hinterland is precisely the non-metro counties). fips state = first 2 digits.
    state_gdp = gdp.groupby(gdp.index.str[:2]).sum()
    state_pop = pop.groupby(pop.index.str[:2]).sum()

    cap = CAPITAL_COUNTY_FIPS
    rows = []
    for (usps, mid), g in d.groupby(["state_usps", "metro_id"]):
        sfips = g["FIPS State Code"].iloc[0]
        rows.append({
            "state_usps": usps,
            "state_name": geo.US_STATES.get(usps, usps),
            "metro_id": mid,
            "metro_name": g["metro_name"].iloc[0],
            "metro_level": g["metro_level"].iloc[0],
            "in_state_gdp": float(g["gdp"].sum(skipna=True)),
            "in_state_pop": float(g["pop"].sum(skipna=True)),
            "county_count": int(len(g)),
            "has_state_capital": bool((g["fips"] == cap.get(usps)).any()),
            "state_total_gdp": float(state_gdp.get(sfips, float("nan"))),
            "state_total_pop": float(state_pop.get(sfips, float("nan"))),
            "year": int(gyear),
        })
    out = pd.DataFrame(rows)
    out = out[(out["in_state_gdp"] > 0) & (out["in_state_pop"] > 0)]
    return out.sort_values(["state_usps", "in_state_gdp"],
                           ascending=[True, False]).reset_index(drop=True)


def load_us_metros() -> pd.DataFrame:
    return load_processed(DATASET_ID)


def build() -> Path:
    acquire()
    df = compile_us_metros(RAW)
    out = get_dataset(DATASET_ID).processed_path
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Compiled {DATASET_ID}: {len(df)} state×metro rows, "
          f"{df['state_usps'].nunique()} states -> {out}")
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        print(__doc__)
