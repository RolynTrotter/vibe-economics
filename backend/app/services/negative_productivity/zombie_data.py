"""Zombie-firm data for the negative-productivity service (ticket 0010, lens 2).

A **zombie firm** (BIS — Banerjee & Hofmann 2018/2020) is an old firm whose
operating earnings don't even cover its interest: interest-coverage ratio
(EBIT ÷ interest expense) **< 1 for ≥3 consecutive years**, firm age ≥10 years.
It's alive only by rolling over debt — the corporate-balance-sheet face of
"negative productivity": capital and labour stuck in value-destroying uses.

Source: **SEC EDGAR XBRL "frames" API** (`data.sec.gov`), public domain. Each
annual frame returns one value per filer for a us-gaap concept:
- `OperatingIncomeLoss`  → EBIT proxy.
- `InterestExpense`      → interest expense.
The interest-coverage ratio is EBIT ÷ interest (computed only where interest > 0).
XBRL is mandated from ~2009, so the panel is the US-listed universe 2009→present.

`build()` owns the multi-call flow (one frame per concept per year, cached):

    python -m app.services.negative_productivity.zombie_data build
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd

from app.core.catalog import PROCESSED_DIR, RAW_DIR
from app.core.datasets import load_processed

DATASET_ID = "sec_zombie_fundamentals"
RAW = RAW_DIR / DATASET_ID

# SEC asks for a descriptive User-Agent with contact info (fair-use; no key).
_UA = {"User-Agent": "vibe-economics research (rolyntrotter@gmail.com)"}
FRAMES = "https://data.sec.gov/api/xbrl/frames/us-gaap/{concept}/USD/CY{year}.json"

EBIT_CONCEPT = "OperatingIncomeLoss"
INTEREST_CONCEPT = "InterestExpense"
START_YEAR = 2009
END_YEAR = 2025  # incomplete recent years are flagged downstream by coverage


# --------------------------------------------------------------------------- #
# Acquire (network) — cache one raw JSON per concept-year
# --------------------------------------------------------------------------- #
def _fetch_frame(client: httpx.Client, concept: str, year: int) -> dict | None:
    """Fetch one CY frame; returns parsed JSON, or None if the frame doesn't exist."""
    resp = client.get(FRAMES.format(concept=concept, year=year), headers=_UA)
    if resp.status_code == 404:
        return None  # future / not-yet-published year
    resp.raise_for_status()
    return resp.json()


def acquire() -> list[Path]:
    """Fetch EBIT + interest frames for each year, caching each raw JSON."""
    RAW.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with httpx.Client(timeout=90.0) as client:
        for concept in (EBIT_CONCEPT, INTEREST_CONCEPT):
            for year in range(START_YEAR, END_YEAR + 1):
                payload = _fetch_frame(client, concept, year)
                if payload is None:
                    continue
                dest = RAW / f"{concept}_{year}.json"
                dest.write_text(json.dumps(payload))
                paths.append(dest)
    return paths


# --------------------------------------------------------------------------- #
# Compile (raw frames -> tidy per-firm-year panel)
# --------------------------------------------------------------------------- #
def _read_concept(raw_dir: Path, concept: str) -> dict[tuple[int, int], dict]:
    """Map (cik, year) -> {val, name, loc} for one concept across cached year files."""
    out: dict[tuple[int, int], dict] = {}
    for fp in sorted(raw_dir.glob(f"{concept}_*.json")):
        year = int(fp.stem.rsplit("_", 1)[1])
        payload = json.loads(fp.read_text())
        for d in payload.get("data", []):
            out[(d["cik"], year)] = {
                "val": d["val"],
                "name": d.get("entityName", ""),
                "loc": d.get("loc"),
            }
    return out


def compile_zombie(raw_dir: str | Path = RAW) -> pd.DataFrame:
    """Join EBIT + interest frames -> tidy panel (cik, name, loc, year, ebit, interest, icr).

    Keeps only firm-years with interest expense > 0 (interest coverage is otherwise
    undefined, and a firm with ~no debt is not a zombie candidate)."""
    raw_dir = Path(raw_dir)
    if not any(raw_dir.glob("*.json")):
        raise FileNotFoundError(
            f"No raw SEC frames under {raw_dir}. Run: "
            f"python -m app.services.negative_productivity.zombie_data build"
        )
    ebit = _read_concept(raw_dir, EBIT_CONCEPT)
    interest = _read_concept(raw_dir, INTEREST_CONCEPT)

    rows: list[dict] = []
    for (cik, year), ie in interest.items():
        eb = ebit.get((cik, year))
        if eb is None:
            continue
        interest_val = ie["val"]
        if interest_val is None or interest_val <= 0:
            continue
        rows.append(
            {
                "cik": cik,
                "name": eb["name"] or ie["name"],
                "loc": eb["loc"] or ie["loc"],
                "year": year,
                "ebit": float(eb["val"]),
                "interest": float(interest_val),
                "icr": float(eb["val"]) / float(interest_val),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("Compiled zombie panel is empty — check the raw frames.")
    return df.sort_values(["cik", "year"]).reset_index(drop=True)


def load_panel() -> pd.DataFrame:
    """Load the compiled per-firm-year panel (cached)."""
    return load_processed(DATASET_ID)


# --------------------------------------------------------------------------- #
# Build entrypoint
# --------------------------------------------------------------------------- #
def build() -> Path:
    acquire()
    df = compile_zombie()
    out = PROCESSED_DIR / f"{DATASET_ID}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Built {DATASET_ID}: {len(df)} firm-years, "
          f"{df['cik'].nunique()} firms, {df['year'].min()}–{df['year'].max()} -> {out}")
    return out


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        print(__doc__)
