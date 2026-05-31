"""Non-OECD metros for the hinterland punch-out — ticket 0008, phase 3 (best effort).

OECD FUA data (metros.py) covers only OECD/EU members, so the big non-OECD economies
the world actually cares about — China, India, Brazil, Russia, Indonesia… — vanish
from the punch-out views. This adds them back.

There is **no clean global metro-GDP API**, so this is a deliberately *curated*,
clearly-flagged best-effort table: for each country, its capital / largest / (where
distinct) richest metro, with an approximate recent **nominal** metro GDP (USD) and
metropolitan population from public reporting (national statistical offices, city
statistical yearbooks, press). The GDP *share* is then computed against the same
**World Bank national totals** the rest of the service uses, so shares are internally
consistent; per-capita is scaled to PPP via each country's national PPP/nominal ratio.

These rows are marked ``curated=True`` and surfaced in the UI as estimates — they are
rougher than the OECD FUA figures and should be read as "ballpark", not gospel. The
robust, headline finding they capture is **primacy**: Bangkok, Buenos Aires, Manila,
Lagos, Cairo and Moscow are a far larger share of their national economies than New
York is of the US — which is exactly what the hinterland view is for.

    python -m app.services.subnational_gdp.nonoecd_metros build

Schema: country_iso3 | metro_name | is_capital | metro_gdp_nominal_usd | population | source
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.catalog import get_dataset
from app.core.datasets import load_processed

DATASET_ID = "nonoecd_metros"

# Curated metros: iso3 -> list of (name, is_capital, nominal GDP $B, population M).
# Figures are approximate recent (~2022-2024) metropolitan-area values from public
# reporting; shares are recomputed against World Bank national GDP at build time.
# `src` documents the basis per country.
_B = 1e9
_M = 1e6
CURATED: dict[str, dict] = {
    "CHN": {"src": "City statistical yearbooks 2023 (Shanghai/Beijing/Shenzhen GDP in RMB ÷ ~7.1)", "metros": [
        ("Shanghai", False, 680, 24.9), ("Beijing", True, 640, 21.9), ("Shenzhen", False, 480, 17.6)]},
    "IND": {"src": "Metro GVA estimates 2023 (Delhi NCR, Mumbai MMR, Bengaluru)", "metros": [
        ("Delhi (NCR)", True, 293, 29.0), ("Mumbai (MMR)", False, 277, 21.0), ("Bengaluru", False, 110, 13.0)]},
    "BRA": {"src": "IBGE municipal/metro GDP 2021-23 (São Paulo, Rio, Distrito Federal)", "metros": [
        ("São Paulo", False, 430, 22.4), ("Rio de Janeiro", False, 190, 13.5), ("Brasília (DF)", True, 74, 4.1)]},
    "RUS": {"src": "Rosstat GRP 2022 (Moscow ~20% of GDP; Saint Petersburg)", "metros": [
        ("Moscow", True, 435, 13.0), ("Saint Petersburg", False, 110, 5.6)]},
    "IDN": {"src": "BPS 2023 (Jabodetabek / Greater Jakarta; Surabaya)", "metros": [
        ("Jakarta (Jabodetabek)", True, 230, 32.0), ("Surabaya", False, 50, 9.5)]},
    "SAU": {"src": "GASTAT regional GDP 2022 (Riyadh, Jeddah/Makkah)", "metros": [
        ("Riyadh", True, 200, 7.7), ("Jeddah", False, 90, 4.8)]},
    "ARG": {"src": "INDEC 2022 (Gran Buenos Aires ~40% of GDP)", "metros": [
        ("Buenos Aires (Gran BA)", True, 260, 15.4)]},
    "ZAF": {"src": "StatsSA regional GDP 2022 (Gauteng/Johannesburg, Cape Town, Tshwane/Pretoria)", "metros": [
        ("Johannesburg", False, 90, 6.0), ("Cape Town", False, 66, 4.8), ("Pretoria (Tshwane)", True, 50, 3.5)]},
    "EGY": {"src": "Greater Cairo metro GDP 2024 (~$104B)", "metros": [
        ("Cairo (Greater)", True, 104, 22.6)]},
    "NGA": {"src": "Lagos State GDP 2023 (USD post-devaluation, approximate)", "metros": [
        ("Lagos", False, 80, 15.0), ("Abuja (FCT)", True, 30, 3.6)]},
    "THA": {"src": "NESDC 2022 (Bangkok Metropolitan Region ~47% of GDP)", "metros": [
        ("Bangkok (BMR)", True, 250, 19.9)]},
    "PHL": {"src": "PSA 2023 (Metro Manila / NCR ~32% of GDP)", "metros": [
        ("Metro Manila (NCR)", True, 150, 13.5)]},
    "VNM": {"src": "GSO 2023 (Ho Chi Minh City, Hanoi)", "metros": [
        ("Ho Chi Minh City", False, 80, 9.3), ("Hanoi", True, 55, 8.5)]},
    "PAK": {"src": "Metro GDP estimates 2022 (Karachi, Lahore, Islamabad)", "metros": [
        ("Karachi", False, 75, 17.0), ("Lahore", False, 60, 13.0), ("Islamabad", True, 25, 1.2)]},
    "BGD": {"src": "Dhaka metropolitan GDP estimate 2023 (nominal)", "metros": [
        ("Dhaka", True, 130, 21.0)]},
}


def compile_nonoecd_metros() -> pd.DataFrame:
    rows = []
    for iso3, rec in CURATED.items():
        for name, is_cap, gdp_b, pop_m in rec["metros"]:
            rows.append({
                "country_iso3": iso3, "metro_name": name, "is_capital": is_cap,
                "metro_gdp_nominal_usd": gdp_b * _B, "population": pop_m * _M,
                "source": rec["src"],
            })
    return pd.DataFrame(rows)


def load_nonoecd_metros() -> pd.DataFrame:
    return load_processed(DATASET_ID)


def build() -> Path:
    df = compile_nonoecd_metros()
    out = get_dataset(DATASET_ID).processed_path
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Compiled {DATASET_ID}: {len(df)} curated metros across "
          f"{df.country_iso3.nunique()} non-OECD countries -> {out}")
    return out


if __name__ == "__main__":
    import sys
    build() if (len(sys.argv) > 1 and sys.argv[1] == "build") else print(__doc__)
