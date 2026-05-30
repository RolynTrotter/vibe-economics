"""OECD Functional Urban Area (FUA) metros — the data behind the metro punch-out /
"hinterland" comparison (ticket 0008, extends the subnational-GDP service).

One consistent source, one methodology, across the US, Europe, Japan, Korea, etc.:
the OECD **FUA "Economy"** table (`DSD_FUA_ECO@DF_ECONOMY`). For every metro it gives
GDP in PPP USD, GDP-per-person PPP, and — crucially — GDP as a **% of national
value**, which is exactly the carve-out we need to "punch out" a metro from its
country without any cross-source subtraction. Metro population is derived as
GDP / GDP-per-person.

National totals (to subtract from) come from the same key-free **World Bank WDI**
series the parent service uses, so the un-punched numbers stay continuous with the
existing ladder.

    python -m app.services.subnational_gdp.metros build   # acquire + compile + parquet

Tidy schema (one row per FUA; national totals denormalised onto each row):

    country_iso3 | country_name | nat_gdp_nominal_usd | nat_gdp_ppp_usd | nat_population
                 | fua_code | fua_name | is_capital | gdp_share_pct
                 | fua_gdp_ppp_usd | fua_population | year

- ``gdp_share_pct``     FUA GDP as % of national GDP (OECD PT_NAT). The carve-out.
- ``is_capital``        True for the FUA containing the national capital.
- ``fua_population``    derived: fua_gdp_ppp_usd / GDP-per-person (PPP).

Coverage is OECD/EU members only — non-OECD countries (China, India, Brazil, …)
have no FUA data and are simply absent here (hidden in the punch-out view).
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import httpx
import pandas as pd

from app.core.catalog import RAW_DIR, get_dataset
from app.core.datasets import load_processed

DATASET_ID = "subnational_metros"
RAW = RAW_DIR / DATASET_ID

OECD_FUA_ECONOMY = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.CFE.EDS,DSD_FUA_ECO@DF_ECONOMY,1.1/all"
)
WB = "https://api.worldbank.org/v2"
WB_GDP_NOMINAL = "NY.GDP.MKTP.CD"
WB_GDP_PPP = "NY.GDP.MKTP.PP.CD"
WB_POP = "SP.POP.TOTL"

# OECD FUA country prefix -> World Bank ISO3.
PREFIX_TO_ISO3: dict[str, str] = {
    "AT": "AUT", "BE": "BEL", "BG": "BGR", "CH": "CHE", "CZ": "CZE", "DE": "DEU",
    "DK": "DNK", "EE": "EST", "EL": "GRC", "ES": "ESP", "FI": "FIN", "FR": "FRA",
    "HR": "HRV", "HU": "HUN", "IE": "IRL", "IT": "ITA", "JPN": "JPN", "KOR": "KOR",
    "LT": "LTU", "LU": "LUX", "LV": "LVA", "NL": "NLD", "NO": "NOR", "NZL": "NZL",
    "PL": "POL", "PT": "PRT", "RO": "ROU", "SE": "SWE", "SI": "SVN", "SK": "SVK",
    "TR": "TUR", "UK": "GBR", "USA": "USA",
}

# The capital's FUA code. Pattern is "<prefix>001F" (3-digit) or "<prefix>01F"
# (3-letter prefixes use 2 digits), with two exceptions where the capital is not
# the principal/largest metro.
_CAPITAL_OVERRIDES = {"USA": "USA04F", "NZL": "NZL03F"}  # Washington, Wellington


def _capital_code(prefix: str) -> str:
    if prefix in _CAPITAL_OVERRIDES:
        return _CAPITAL_OVERRIDES[prefix]
    return f"{prefix}{'001F' if len(prefix) == 2 else '01F'}"


def _prefix(code: str) -> str:
    return re.match(r"^[A-Za-z]+", code).group(0)


_UA = {"User-Agent": "vibe-economics/0.1"}


# --------------------------------------------------------------------------- #
# Acquire
# --------------------------------------------------------------------------- #
def acquire() -> dict[str, Path]:
    RAW.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    csv_accept = "application/vnd.sdmx.data+csv"
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        # Values: all years, code labels (OECD streams large responses code-only).
        r = client.get(OECD_FUA_ECONOMY, headers={**_UA, "Accept": csv_accept})
        r.raise_for_status()
        paths["fua"] = RAW / "fua_economy.csv"
        paths["fua"].write_text(r.text)

        # Names: a single year with both labels (FUA names are stable across years).
        rn = client.get(OECD_FUA_ECONOMY,
                        params={"startPeriod": "2021", "endPeriod": "2021"},
                        headers={**_UA, "Accept": f"{csv_accept}; labels=both"})
        rn.raise_for_status()
        paths["names"] = RAW / "fua_names.csv"
        paths["names"].write_text(rn.text)

        for ind, tag in ((WB_GDP_NOMINAL, "wb_gdp"), (WB_GDP_PPP, "wb_gdp_ppp"),
                         (WB_POP, "wb_pop")):
            d = client.get(f"{WB}/country/all/indicator/{ind}",
                           params={"format": "json", "per_page": "20000", "mrv": "6"},
                           headers=_UA)
            d.raise_for_status()
            paths[tag] = RAW / f"{tag}.json"
            paths[tag].write_text(d.text)
    return paths


# --------------------------------------------------------------------------- #
# Compile
# --------------------------------------------------------------------------- #
def _wb_latest(path: Path) -> dict[str, float]:
    import json
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


def _fua_names(path: Path) -> dict[str, str]:
    """code -> display name, from the both-labelled CSV ('CODE: Name' cells)."""
    names: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(Path(path).read_text())):
        code, _, name = row["REF_AREA: Reference area"].partition(": ")
        if code and name:
            names[code] = name
    return names


def _parse_fua_economy(values_path: Path, names: dict[str, str]) -> dict[str, dict]:
    """Per-FUA latest-year GDP (USD PPP), GDP share of national (%), and per-person
    GDP, from the code-labelled values CSV."""
    want = {
        ("GDP", "USD_PPP"): "gdp_ppp",
        ("GDP", "PT_NAT"): "share",
        ("GDP", "USD_PPP_PS"): "gdp_pp",
    }
    store: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(Path(values_path).read_text())):
        code = row["REF_AREA"]
        key = want.get((row["MEASURE"], row["UNIT_MEASURE"]))
        if key is None:
            continue
        try:
            val = float(row["OBS_VALUE"]) * 10 ** int(row["UNIT_MULT"])
        except (ValueError, KeyError):
            continue
        year = int(row["TIME_PERIOD"])
        rec = store.setdefault(code, {"name": names.get(code, code)})
        cur = rec.get(key)
        if cur is None or year > cur[0]:
            rec[key] = (year, val)
    return store


def compile_metros(raw_dir: str | Path = RAW) -> pd.DataFrame:
    raw_dir = Path(raw_dir)
    names = _fua_names(raw_dir / "fua_names.csv")
    store = _parse_fua_economy(raw_dir / "fua_economy.csv", names)
    nat_nom = _wb_latest(raw_dir / "wb_gdp.json")
    nat_ppp = _wb_latest(raw_dir / "wb_gdp_ppp.json")
    nat_pop = _wb_latest(raw_dir / "wb_pop.json")

    rows = []
    for code, rec in store.items():
        prefix = _prefix(code)
        iso3 = PREFIX_TO_ISO3.get(prefix)
        if iso3 is None or "gdp_ppp" not in rec or "share" not in rec:
            continue
        year, gdp_ppp = rec["gdp_ppp"]
        share = rec["share"][1]
        pop = None
        if "gdp_pp" in rec and rec["gdp_pp"][1]:
            pop = gdp_ppp / rec["gdp_pp"][1]
        rows.append({
            "country_iso3": iso3,
            "nat_gdp_nominal_usd": nat_nom.get(iso3),
            "nat_gdp_ppp_usd": nat_ppp.get(iso3),
            "nat_population": nat_pop.get(iso3),
            "fua_code": code,
            "fua_name": rec["name"],
            "is_capital": code == _capital_code(prefix),
            "gdp_share_pct": share,
            "fua_gdp_ppp_usd": gdp_ppp,
            "fua_population": pop,
            "year": year,
        })
    df = pd.DataFrame(rows)
    df = df.dropna(subset=["nat_gdp_ppp_usd", "nat_population"])
    return df.sort_values(["country_iso3", "gdp_share_pct"],
                          ascending=[True, False]).reset_index(drop=True)


def load_metros() -> pd.DataFrame:
    return load_processed(DATASET_ID)


def build() -> Path:
    acquire()
    df = compile_metros(RAW)
    out = get_dataset(DATASET_ID).processed_path
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    n_countries = df["country_iso3"].nunique()
    print(f"Compiled {DATASET_ID}: {len(df)} FUAs across {n_countries} countries -> {out}")
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        print(__doc__)
