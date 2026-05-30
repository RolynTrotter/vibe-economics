"""Data loading + dataset compilers for the safe-withdrawal service.

The service now runs on the **Jordà-Schularick-Taylor Macrohistory** database
(`compile_jst`), which gives consistent annual total returns for 18 developed
economies (1870–2020) and lets us build a *real* international equity sleeve — so
a three-fund portfolio genuinely differs from a US 60/40 instead of collapsing
into it.

Tidy output schema (all *nominal* annual figures; real returns derived in model.py):

    year | us_stock | intl_stock | bond | inflation

- us_stock:   USA equity total return (eq_tr).
- intl_stock: GDP-weighted developed-ex-US equity total return, **converted to USD**
              (a US investor's experience, including currency moves). Weights are
              prior-year total real GDP (rgdpmad * pop) over the countries that
              have data that year, so coverage scales from a handful in the 1870s
              to all 17 ex-US markets in recent decades.
- bond:       USA government bond total return (bond_tr).
- inflation:  USA CPI change.

`compile_shiller` is retained as a US-only alternative / cross-check.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.core.datasets import load_processed

DATASET_ID = "jst_returns"


# --------------------------------------------------------------------------- #
# JST Macrohistory compiler (primary)
# --------------------------------------------------------------------------- #
def _usd_return(eq_tr_local: float, xrusd_prev: float, xrusd_cur: float) -> float:
    """Convert a local-currency equity return to a US investor's USD return.

    xrusd is local currency per USD. A US investor buys foreign equity with USD
    (gets xrusd_prev local units), earns the local return, then converts back at
    xrusd_cur:  usd = (1 + eq_tr_local) * xrusd_prev / xrusd_cur - 1.
    A strengthening foreign currency (xrusd falling) adds to the USD return.
    """
    if pd.isna(eq_tr_local) or pd.isna(xrusd_prev) or pd.isna(xrusd_cur) or xrusd_cur == 0:
        return float("nan")
    return (1.0 + eq_tr_local) * xrusd_prev / xrusd_cur - 1.0


def compile_jst(raw_path: str | Path) -> pd.DataFrame:
    """Compile JST Macrohistory xlsx -> US-investor annual tidy returns table."""
    df = pd.read_excel(raw_path)
    df = df.rename(columns={"pop": "population"})
    keep = ["year", "iso", "eq_tr", "bond_tr", "cpi", "xrusd", "rgdpmad", "population"]
    df = df[keep].copy()
    for c in ("eq_tr", "bond_tr", "cpi", "xrusd", "rgdpmad", "population"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["year"] = df["year"].astype(int)

    # Total real GDP per country-year (Maddison per-capita * population); used as
    # the (prior-year) weight for the international equity aggregate.
    df["gdp_tot"] = df["rgdpmad"] * df["population"]

    usa = df[df["iso"] == "USA"].set_index("year")
    intl = df[df["iso"] != "USA"].copy()

    # Per-country prior-year FX and GDP weight, aligned to the return year.
    intl = intl.sort_values(["iso", "year"])
    intl["xrusd_prev"] = intl.groupby("iso")["xrusd"].shift(1)
    intl["gdp_prev"] = intl.groupby("iso")["gdp_tot"].shift(1)
    intl["usd_ret"] = [
        _usd_return(e, p, c)
        for e, p, c in zip(intl["eq_tr"], intl["xrusd_prev"], intl["xrusd"])
    ]

    # GDP-weighted ex-US equity (USD) per year over countries with data that year.
    def _weighted(group: pd.DataFrame) -> float:
        g = group.dropna(subset=["usd_ret", "gdp_prev"])
        g = g[g["gdp_prev"] > 0]
        if g.empty:
            return float("nan")
        w = g["gdp_prev"] / g["gdp_prev"].sum()
        return float((w * g["usd_ret"]).sum())

    intl_by_year = intl.groupby("year").apply(_weighted, include_groups=False)

    rows = []
    for y in sorted(usa.index):
        if (y - 1) not in usa.index:
            continue
        us_stock = usa.at[y, "eq_tr"]
        bond = usa.at[y, "bond_tr"]
        cpi0, cpi1 = usa.at[y - 1, "cpi"], usa.at[y, "cpi"]
        inflation = (cpi1 / cpi0 - 1.0) if pd.notna(cpi0) and pd.notna(cpi1) else np.nan
        intl_stock = intl_by_year.get(y, np.nan)
        rows.append((int(y), us_stock, intl_stock, bond, inflation))

    out = pd.DataFrame(
        rows, columns=["year", "us_stock", "intl_stock", "bond", "inflation"]
    )
    return out.dropna().reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Shiller compiler (retained US-only alternative / cross-check)
# --------------------------------------------------------------------------- #
def bond_year_return(y0: float, y1: float, n: int = 10) -> float:
    """Total annual return of a 10-yr par bond when the yield moves y0 -> y1.

    Priced at par (=1) with annual coupon = start yield y0, revalued at the
    end-of-year yield y1 over n years. Yields are decimals. (Used by the Shiller
    compiler; JST ships bond_tr directly.)
    """
    if pd.isna(y0) or pd.isna(y1):
        return float("nan")
    coupon = y0
    t = np.arange(1, n + 1)
    price_end = (coupon / (1 + y1) ** t).sum() + 1 / (1 + y1) ** n
    return float(price_end + coupon - 1)


def compile_shiller(raw_path: str | Path) -> pd.DataFrame:
    """Compile the monthly Shiller CSV -> annual US-only tidy returns table.

    Schema: year | us_stock | bond | inflation  (no international sleeve).
    """
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

    # The mirror pads not-yet-reported months with 0.0 — treat 0 as missing.
    for c in ("price", "cpi", "gs10"):
        df.loc[df[c] == 0, c] = np.nan

    df["_div_month"] = df["dividend"] / 12.0
    ann_div = df.groupby("year")["_div_month"].sum()

    dec = df[df["month"] == 12].dropna(subset=["price", "cpi", "gs10"]).set_index("year")

    rows = []
    for y in sorted(dec.index):
        if (y - 1) not in dec.index:
            continue
        p0, p1 = dec.at[y - 1, "price"], dec.at[y, "price"]
        cpi0, cpi1 = dec.at[y - 1, "cpi"], dec.at[y, "cpi"]
        y0 = dec.at[y - 1, "gs10"] / 100.0
        y1 = dec.at[y, "gs10"] / 100.0
        div = ann_div.get(y, np.nan)
        if not div or np.isnan(div):
            continue
        us_stock = (p1 + div) / p0 - 1.0
        inflation = cpi1 / cpi0 - 1.0
        bond = bond_year_return(y0, y1)
        rows.append((int(y), us_stock, bond, inflation))

    out = pd.DataFrame(rows, columns=["year", "us_stock", "bond", "inflation"])
    return out.dropna().reset_index(drop=True)


def load_returns() -> pd.DataFrame:
    """Load the compiled annual returns table (cached)."""
    return load_processed(DATASET_ID)
