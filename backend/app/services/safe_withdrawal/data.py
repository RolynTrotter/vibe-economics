"""Data loading + the Shiller compiler for the safe-withdrawal service.

`compile_shiller` (referenced from data/catalog.yaml) turns Shiller's monthly
S&P 500 series (the github.com/datasets/s-and-p-500 CSV mirror of Yale's
ie_data) into an annual tidy table:

    year | stock_return | bond_return | inflation

All three are *nominal* annual figures (real returns are derived in model.py).
- stock_return: S&P total return (price change + reinvested dividends), Dec→Dec.
- bond_return:  10-year Treasury total return, modelled as a par bond at the
                start-of-year yield revalued at the end-of-year yield
                (constant-maturity approximation). Yields = "Long Interest Rate".
- inflation:    CPI change, Dec→Dec.

Raw CSV columns:
    Date, SP500, Dividend, Earnings, Consumer Price Index, Long Interest Rate,
    Real Price, Real Dividend, Real Earnings, PE10
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.core.datasets import load_processed

DATASET_ID = "shiller_returns"


def bond_year_return(y0: float, y1: float, n: int = 10) -> float:
    """Total annual return of a 10-yr par bond when the yield moves y0 -> y1.

    The bond is priced at par (=1) at the start of the year with an annual coupon
    equal to the start yield y0, then revalued at the end-of-year yield y1 over n
    years (constant-maturity approximation). Return = clean price change + coupon.
    Yields are decimals (e.g. 0.045 for 4.5%).
    """
    if pd.isna(y0) or pd.isna(y1):
        return float("nan")
    coupon = y0
    t = np.arange(1, n + 1)
    price_end = (coupon / (1 + y1) ** t).sum() + 1 / (1 + y1) ** n
    return float(price_end + coupon - 1)


def compile_shiller(raw_path: str | Path) -> pd.DataFrame:
    """Compile the monthly Shiller CSV -> annual tidy returns table."""
    df = pd.read_csv(raw_path)
    df.columns = [str(c).strip() for c in df.columns]

    rename = {
        "SP500": "price",
        "Dividend": "dividend",
        "Consumer Price Index": "cpi",
        "Long Interest Rate": "gs10",
    }
    df = df.rename(columns=rename)
    df["dt"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["dt"])
    df["year"] = df["dt"].dt.year
    df["month"] = df["dt"].dt.month
    for c in ("price", "dividend", "cpi", "gs10"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # The mirror pads the latest, not-yet-reported months with 0.0 — treat 0 as
    # missing for price/cpi/gs10 so incomplete trailing months don't poison a year.
    for c in ("price", "cpi", "gs10"):
        df.loc[df[c] == 0, c] = np.nan

    # Annual dividend = sum of monthly (annualized dividend / 12) over the year.
    df["_div_month"] = df["dividend"] / 12.0
    ann_div = df.groupby("year")["_div_month"].sum()

    # December observations carry the year-end price / CPI / yield.
    dec = (
        df[df["month"] == 12]
        .dropna(subset=["price", "cpi", "gs10"])
        .set_index("year")
    )

    rows = []
    for y in sorted(dec.index):
        if (y - 1) not in dec.index:
            continue
        p0, p1 = dec.at[y - 1, "price"], dec.at[y, "price"]
        cpi0, cpi1 = dec.at[y - 1, "cpi"], dec.at[y, "cpi"]
        y0 = dec.at[y - 1, "gs10"] / 100.0
        y1 = dec.at[y, "gs10"] / 100.0
        div = ann_div.get(y, np.nan)
        if not div or np.isnan(div):  # incomplete (trailing) year — skip
            continue
        stock = (p1 + div) / p0 - 1.0
        inflation = cpi1 / cpi0 - 1.0
        bond = bond_year_return(y0, y1)
        rows.append((int(y), stock, bond, inflation))

    out = pd.DataFrame(rows, columns=["year", "stock_return", "bond_return", "inflation"])
    return out.dropna().reset_index(drop=True)


def load_returns() -> pd.DataFrame:
    """Load the compiled annual returns table (cached)."""
    return load_processed(DATASET_ID)
