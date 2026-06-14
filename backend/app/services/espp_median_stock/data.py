"""Data acquisition + compiler for the ESPP / median-stock service.

Question this dataset powers
----------------------------
How does the *median* S&P 500 stock do over a one-year holding period, versus the
index itself? Stock returns are heavily right-skewed (a few huge winners carry the
cap-weighted index), so the typical — median — stock tends to *lag* the index.
That gap is what an ESPP discount has to overcome when a plan forces you to hold a
single employer stock for a year before selling.

Sources (multi-call, so build via the service entrypoint, not the single-URL CLI)
---------------------------------------------------------------------------------
- Current S&P 500 constituents: the GitHub `datasets/s-and-p-500-companies` mirror
  (Symbol, Security, GICS Sector, Date added, ...).
- Per-stock monthly **adjusted close** (split- *and* dividend-adjusted = total
  return) from the key-free Yahoo Finance chart API (`range=max&interval=1mo`).
- Benchmark: **SPY** (SPDR S&P 500 ETF) monthly adjusted close. SPY's adjusted
  close reinvests dividends, so it is a total-return S&P 500 series on the exact
  same Yahoo footing as the single stocks (Yahoo's ^SP500TR is served only
  sparsely, with no year-end points). The ~0.09%/yr expense drag is negligible
  here and arguably more realistic than a frictionless index.

    python -m app.services.espp_median_stock.data build   # acquire + compile + write

Tidy processed schema (long; one row per stock-year and one per index-year)
---------------------------------------------------------------------------
    ticker | year | total_return | kind

- ticker:       stock symbol, or "^SP500TR" for the benchmark row.
- year:         calendar year of the return.
- total_return: Dec(t-1) -> Dec(t) total return (reinvested dividends), decimal.
- kind:         "stock" or "index".

IMPORTANT — survivorship bias
-----------------------------
The universe is *today's* S&P 500 members. Companies that were dropped, acquired,
or went bankrupt over the window are absent, and a name only contributes in years
it was already public. Survivors skew up, so the real median stock did **worse**
than what this panel shows. That makes the headline ("the median stock lags the
index") a *conservative* lower bound on the effect — the honest direction for an
ESPP risk argument. Flagged the same way the zombie-firm lens flags its XBRL
universe (ticket 0010).
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from app.core.catalog import get_dataset
from app.core.datasets import load_processed

DATASET_ID = "sp500_constituent_returns"
MONTHLY_DATASET_ID = "sp500_monthly_levels"
INDEX_TICKER = "SPY"  # SPY adjusted close = total-return S&P 500 (see module docstring)

_CONSTITUENTS_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "main/data/constituents.csv"
)
_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# Yahoo's edge throttles requests without a browser-like User-Agent.
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


# --------------------------------------------------------------------------- #
# Acquire
# --------------------------------------------------------------------------- #
def _raw_dir() -> Path:
    d = get_dataset(DATASET_ID).raw_path
    if d is None:
        raise ValueError(f"{DATASET_ID} has no raw path configured.")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fetch_constituents(client: httpx.Client) -> pd.DataFrame:
    resp = client.get(_CONSTITUENTS_URL)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df.columns = [c.strip() for c in df.columns]
    return df


def _fetch_monthly(client: httpx.Client, symbol: str) -> pd.DataFrame | None:
    """Monthly adjusted close for one symbol -> DataFrame[date, adjclose]; None on miss."""
    # Yahoo wants the literal '^' for indices; URL-encoding it breaks the lookup.
    url = _YAHOO_CHART.format(symbol=symbol)
    for attempt in range(4):
        try:
            resp = client.get(url, params={"range": "max", "interval": "1mo"})
            if resp.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            resp.raise_for_status()
            payload = resp.json()
            result = (payload.get("chart") or {}).get("result")
            if not result:
                return None
            r = result[0]
            ts = r.get("timestamp")
            if not ts:
                return None
            ind = r.get("indicators", {})
            close = ind.get("quote", [{}])[0].get("close")  # split-adjusted price
            adj = None
            if "adjclose" in ind and ind["adjclose"]:
                adj = ind["adjclose"][0].get("adjclose")
            if adj is None:  # TR indices carry no separate adjclose; close already includes divs
                adj = close
            dates = pd.to_datetime(pd.Series(ts), unit="s", utc=True).dt.tz_localize(None)
            # adjclose = total return (split + dividend adjusted); close = split-adjusted
            # *price* (no dividend adjustment) — needed for the ESPP lookback, which
            # compares actual share prices, not total-return levels.
            out = pd.DataFrame({"date": dates, "adjclose": adj, "close": close}).dropna()
            return out if len(out) else None
        except (httpx.HTTPError, ValueError, KeyError):
            time.sleep(1.0 * (attempt + 1))
    return None


def acquire() -> None:
    """Download the constituent list, every member's monthly TR series, and ^SP500TR."""
    raw = _raw_dir()
    with httpx.Client(
        follow_redirects=True, timeout=30.0, headers={"User-Agent": _UA}
    ) as client:
        constituents = _fetch_constituents(client)
        constituents.to_csv(raw / "constituents.csv", index=False)
        symbols = sorted(constituents["Symbol"].dropna().astype(str).unique())
        print(f"constituents: {len(symbols)} symbols")

        # Yahoo uses '-' where the index list uses '.' for share classes (BRK.B -> BRK-B).
        frames: list[pd.DataFrame] = []
        misses: list[str] = []
        for i, sym in enumerate(symbols, 1):
            ysym = sym.replace(".", "-")
            df = _fetch_monthly(client, ysym)
            if df is None:
                misses.append(sym)
            else:
                df["ticker"] = sym
                frames.append(df)
            if i % 50 == 0:
                print(f"  ...{i}/{len(symbols)} fetched ({len(misses)} misses)")
            time.sleep(0.25)  # polite spacing under Yahoo's burst throttle

        prices = pd.concat(frames, ignore_index=True)
        prices.to_parquet(raw / "monthly_prices.parquet", index=False)
        print(f"stock prices: {len(prices)} rows, {prices['ticker'].nunique()} tickers, "
              f"{len(misses)} misses: {misses[:20]}")

        idx = _fetch_monthly(client, INDEX_TICKER)
        if idx is None:
            raise RuntimeError(f"Failed to fetch {INDEX_TICKER} benchmark series.")
        idx["ticker"] = INDEX_TICKER
        idx.to_parquet(raw / "index_prices.parquet", index=False)
        print(f"index {INDEX_TICKER}: {len(idx)} rows "
              f"{idx['date'].min().date()} -> {idx['date'].max().date()}")


# --------------------------------------------------------------------------- #
# Compile
# --------------------------------------------------------------------------- #
def _annual_total_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Calendar-year total returns from monthly adjusted close.

    For each ticker, take the last observation in each December (the year-end
    level), then r_t = level(Dec t) / level(Dec t-1) - 1. A one-year hold maps
    naturally onto a calendar-year return.
    """
    px = prices.copy()
    px["date"] = pd.to_datetime(px["date"])
    px["year"] = px["date"].dt.year
    px["month"] = px["date"].dt.month
    dec = px[px["month"] == 12].sort_values(["ticker", "date"])
    # last December observation per ticker-year = the year-end level
    year_end = dec.groupby(["ticker", "year"], as_index=False).last()
    year_end = year_end.sort_values(["ticker", "year"])
    year_end["prev"] = year_end.groupby("ticker")["adjclose"].shift(1)
    year_end["prev_year"] = year_end.groupby("ticker")["year"].shift(1)
    # only consecutive Decembers form a clean one-year return
    consec = year_end["prev_year"] == year_end["year"] - 1
    out = year_end[consec & year_end["prev"].notna() & (year_end["prev"] > 0)].copy()
    out["total_return"] = out["adjclose"] / out["prev"] - 1.0
    return out[["ticker", "year", "total_return"]].reset_index(drop=True)


def compile_dataset(raw_dir: str | Path) -> pd.DataFrame:
    """Compile raw monthly prices -> tidy annual total-return panel (stocks + index)."""
    raw_dir = Path(raw_dir)
    stock_px = pd.read_parquet(raw_dir / "monthly_prices.parquet")
    index_px = pd.read_parquet(raw_dir / "index_prices.parquet")

    stock_ret = _annual_total_returns(stock_px)
    stock_ret["kind"] = "stock"
    index_ret = _annual_total_returns(index_px)
    index_ret["kind"] = "index"

    out = pd.concat([stock_ret, index_ret], ignore_index=True)
    out = out.sort_values(["kind", "year", "ticker"]).reset_index(drop=True)
    out["total_return"] = out["total_return"].astype(float)
    return out


def _monthly_levels(prices: pd.DataFrame, kind: str) -> pd.DataFrame:
    """One observation per ticker-month (last trading point in the month).

    `mkey` is a dense calendar month index (year*12 + month-1) so a hold of N
    months is exactly `mkey + N` — gaps in a ticker's history are skipped rather
    than mis-aligned. `level` is the split+dividend-adjusted close (total return);
    `price` is the split-adjusted close (no dividend adjustment) used by the ESPP
    lookback, which compares actual share prices. Older raw files without `close`
    fall back to price = level (a small distortion on lookback cases only).
    """
    px = prices.copy()
    if "close" not in px.columns:
        px["close"] = px["adjclose"]
    px["date"] = pd.to_datetime(px["date"])
    px["year"] = px["date"].dt.year
    px["month"] = px["date"].dt.month
    px = px.sort_values(["ticker", "date"])
    last = px.groupby(["ticker", "year", "month"], as_index=False).last()
    last["mkey"] = last["year"] * 12 + (last["month"] - 1)
    last["kind"] = kind
    out = last[["ticker", "mkey", "year", "month", "adjclose", "close", "kind"]]
    return out.rename(columns={"adjclose": "level", "close": "price"})


def compile_monthly(raw_dir: str | Path) -> pd.DataFrame:
    """Compile raw monthly prices -> tidy monthly total-return levels + prices (stocks + index).

    Powers the ESPP Analyzer, which needs arbitrary-horizon (term + holding) returns
    (total-return `level`) and the lookback min(start, purchase) on actual share
    `price`, not just calendar-year returns.
    Schema: ticker | mkey | year | month | level | price | kind (stock | index).
    """
    raw_dir = Path(raw_dir)
    stock_px = pd.read_parquet(raw_dir / "monthly_prices.parquet")
    index_px = pd.read_parquet(raw_dir / "index_prices.parquet")
    stock = _monthly_levels(stock_px, "stock")
    index = _monthly_levels(index_px, "index")
    out = pd.concat([stock, index], ignore_index=True)
    out = out.sort_values(["kind", "ticker", "mkey"]).reset_index(drop=True)
    out["level"] = out["level"].astype(float)
    out["price"] = out["price"].astype(float)
    return out


def _write_processed(ds_id: str, df: pd.DataFrame) -> None:
    entry = get_dataset(ds_id)
    out = entry.processed_path
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Compiled {ds_id}: {len(df)} rows -> {out}")


def build() -> None:
    """End-to-end: acquire raw, compile both the annual panel and the monthly levels."""
    acquire()
    raw_dir = get_dataset(DATASET_ID).raw_path
    _write_processed(DATASET_ID, compile_dataset(raw_dir))
    _write_processed(MONTHLY_DATASET_ID, compile_monthly(raw_dir))


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #
def load_panel() -> pd.DataFrame:
    """Load the compiled annual total-return panel (cached)."""
    return load_processed(DATASET_ID)


def load_monthly() -> pd.DataFrame:
    """Load the compiled monthly total-return levels (cached). Powers the ESPP Analyzer."""
    return load_processed(MONTHLY_DATASET_ID)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    raw_dir = get_dataset(DATASET_ID).raw_path
    if cmd == "acquire":
        acquire()
    elif cmd == "compile":
        _write_processed(DATASET_ID, compile_dataset(raw_dir))
        _write_processed(MONTHLY_DATASET_ID, compile_monthly(raw_dir))
    else:
        build()
