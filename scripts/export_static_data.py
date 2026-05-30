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


def export_shiller_returns() -> None:
    df = pd.read_parquet(ROOT / "data" / "processed" / "shiller_returns.parquet")
    df = df.sort_values("year")
    payload = {
        "dataset": "shiller_returns",
        "source": "Robert J. Shiller, Yale (CSV mirror datasets/s-and-p-500)",
        "first_year": int(df.year.min()),
        "last_year": int(df.year.max()),
        "n_years": int(len(df)),
        "units": "real (CPI-adjusted); withdrawals constant in real terms",
        "definition": (
            "SWR = upper bound on the 4% rule: max constant real withdrawal that "
            "depletes the portfolio to exactly $0 at the horizon."
        ),
        "notes": "Bond = 10yr Treasury par-bond proxy. 3-fund intl equity proxied by US equity.",
        "columns": ["year", "stock_return", "bond_return", "inflation"],
        "rows": [
            [
                int(r.year),
                round(float(r.stock_return), 6),
                round(float(r.bond_return), 6),
                round(float(r.inflation), 6),
            ]
            for r in df.itertuples()
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "shiller_returns.json"
    out.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"wrote {len(payload['rows'])} rows -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    export_shiller_returns()
