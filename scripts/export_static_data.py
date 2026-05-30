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


def export_jst_returns() -> None:
    df = pd.read_parquet(ROOT / "data" / "processed" / "jst_returns.parquet")
    df = df.sort_values("year")
    payload = {
        "dataset": "jst_returns",
        "source": "Jordà-Schularick-Taylor Macrohistory (Rate of Return on Everything, 1870-2015)",
        "first_year": int(df.year.min()),
        "last_year": int(df.year.max()),
        "n_years": int(len(df)),
        "units": "real (CPI-adjusted); withdrawals constant in real terms",
        "definition": (
            "SWR = upper bound on the 4% rule: max constant real withdrawal that "
            "depletes the portfolio to exactly $0 at the horizon."
        ),
        "notes": (
            "US & bond from JST USA series; intl = GDP-weighted developed-ex-US "
            "equity converted to USD. Three-fund = 60/40 equity/bond with equity "
            "split 60/40 US/intl, so it differs from 60-40 only by international "
            "diversification."
        ),
        "columns": ["year", "us_stock", "intl_stock", "bond", "inflation"],
        "rows": [
            [
                int(r.year),
                round(float(r.us_stock), 6),
                round(float(r.intl_stock), 6),
                round(float(r.bond), 6),
                round(float(r.inflation), 6),
            ]
            for r in df.itertuples()
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "jst_returns.json"
    out.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"wrote {len(payload['rows'])} rows -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    export_jst_returns()
