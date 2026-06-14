"""Pure analysis for the ESPP / median-stock service.

No FastAPI, no I/O — every function takes the tidy panel (ticker, year,
total_return, kind) and returns numbers / DataFrames. This is what the tests pin.

The question
------------
For each calendar year, how did the **median** S&P 500 stock do over that one
year (total return, dividends reinvested) versus the **index** (SPY, a total-
return S&P 500)? The median is the experience of a *typical* single stock — the
relevant thing when an ESPP forces you to hold one employer stock for a year.

Two well-known forces pull median ≠ index:
- **Skewness.** A handful of huge winners carry a cap-weighted index, so more than
  half of stocks can lag it. This is strong over long/lifetime horizons; over a
  *single year* it is much milder.
- **Weighting.** The index is cap-weighted; the median (and the cross-sectional
  mean) are effectively equal-weighted, which diverges from cap-weight depending
  on whether mega-caps or the broad middle are leading.

The ESPP lens
-------------
An ESPP typically lets you buy at a discount `d` (commonly 15%). If a plan forces
a one-year hold before you can sell, your return on the cash you put in is

    espp_return = (1 + stock_return) / (1 - d) - 1

(you buy `1/(1-d)` of market value per dollar, then ride the stock for a year).
The discount is a one-time head start of `1/(1-d) - 1` (≈ 17.6% at d=0.15). The
question "is the ESPP worth it under a one-year hold?" becomes: does that head
start outweigh (a) how the typical single stock does vs the index, and (b) the
extra single-stock downside you take on by not just buying the index?

Survivorship caveat (see data.py): the universe is *today's* members, so the
median here is biased upward. Treat "median ≈ / slightly beats index over one
year" as a survivor-friendly read; the true median (with delistings) is worse,
and the left tail is fatter.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_DISCOUNT = 0.15
# Years thinner than this many surviving constituents are dropped: early-90s
# cross-sections are tiny and the most survivorship-skewed.
MIN_STOCKS_PER_YEAR = 30


def _split(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Return (stock rows, index total-return Series indexed by year)."""
    stocks = panel[panel["kind"] == "stock"][["ticker", "year", "total_return"]]
    index = (
        panel[panel["kind"] == "index"]
        .set_index("year")["total_return"]
        .sort_index()
    )
    return stocks, index


def available_years(panel: pd.DataFrame) -> list[int]:
    """Calendar years with both an index return and >= MIN_STOCKS_PER_YEAR stocks."""
    stocks, index = _split(panel)
    counts = stocks.groupby("year")["total_return"].count()
    years = [
        int(y)
        for y, n in counts.items()
        if n >= MIN_STOCKS_PER_YEAR and y in index.index
    ]
    return sorted(years)


def by_year(panel: pd.DataFrame, discount: float = DEFAULT_DISCOUNT) -> pd.DataFrame:
    """Per-year cross-sectional stats of single-stock total returns vs the index.

    Columns: year, n_stocks, index_return, median_stock, mean_stock, p10, p25,
    p75, p90, pct_beat_index, pct_negative, median_espp_return, pct_espp_beat_index.
    """
    stocks, index = _split(panel)
    rows = []
    for y in available_years(panel):
        s = stocks.loc[stocks["year"] == y, "total_return"].to_numpy()
        idx = float(index[y])
        espp = (1.0 + s) / (1.0 - discount) - 1.0
        rows.append(
            {
                "year": y,
                "n_stocks": int(s.size),
                "index_return": idx,
                "median_stock": float(np.median(s)),
                "mean_stock": float(np.mean(s)),
                "p10": float(np.percentile(s, 10)),
                "p25": float(np.percentile(s, 25)),
                "p75": float(np.percentile(s, 75)),
                "p90": float(np.percentile(s, 90)),
                "pct_beat_index": float(np.mean(s > idx)),
                "pct_negative": float(np.mean(s < 0)),
                "median_espp_return": float(np.median(espp)),
                "pct_espp_beat_index": float(np.mean(espp > idx)),
            }
        )
    return pd.DataFrame(rows)


def pooled_distribution(
    panel: pd.DataFrame, discount: float = DEFAULT_DISCOUNT
) -> dict:
    """Pooled (all stock-years) distribution + ESPP outcomes over the usable window.

    Pools every single-stock one-year total return across the eligible years and
    asks: how does a randomly chosen stock-year compare to its year's index, with
    and without the ESPP discount? This is the "if you hold one random member for
    one year" distribution.
    """
    stocks, index = _split(panel)
    years = available_years(panel)
    df = stocks[stocks["year"].isin(years)].copy()
    df["index_return"] = df["year"].map(index)
    r = df["total_return"].to_numpy()
    idx = df["index_return"].to_numpy()
    espp = (1.0 + r) / (1.0 - discount) - 1.0

    head_start = 1.0 / (1.0 - discount) - 1.0
    return {
        "discount": discount,
        "espp_head_start": head_start,  # one-time edge from buying at the discount
        "n_stock_years": int(r.size),
        "first_year": int(min(years)),
        "last_year": int(max(years)),
        # raw single-stock one-year total return distribution
        "stock_median": float(np.median(r)),
        "stock_mean": float(np.mean(r)),
        "stock_p10": float(np.percentile(r, 10)),
        "stock_p25": float(np.percentile(r, 25)),
        "stock_p75": float(np.percentile(r, 75)),
        "stock_p90": float(np.percentile(r, 90)),
        "pct_negative": float(np.mean(r < 0)),
        "pct_loss_gt_discount": float(np.mean(r < -discount)),  # discount fully wiped out
        "pct_beat_index": float(np.mean(r > idx)),
        # the gap a single stock gives up (or gains) vs the index, no discount
        "median_excess_vs_index": float(np.median(r - idx)),
        "mean_excess_vs_index": float(np.mean(r - idx)),
        # with the ESPP discount applied
        "espp_median_return": float(np.median(espp)),
        "espp_mean_return": float(np.mean(espp)),
        "espp_pct_underwater": float(np.mean(espp < 0)),  # lose money on your cash
        "espp_pct_beat_index": float(np.mean(espp > idx)),
        "index_mean": float(np.mean(idx)),
        "index_median": float(np.median(idx)),
    }


def espp_curve(panel: pd.DataFrame, discounts: list[float]) -> pd.DataFrame:
    """How the ESPP verdict shifts with the discount size.

    For each discount, the pooled probability the discounted single stock (held a
    year) beats the index, the probability you still end underwater, and the
    median ESPP return. Lets the widget sweep the discount slider.
    """
    rows = []
    for d in discounts:
        p = pooled_distribution(panel, discount=d)
        rows.append(
            {
                "discount": d,
                "espp_head_start": p["espp_head_start"],
                "espp_median_return": p["espp_median_return"],
                "espp_pct_beat_index": p["espp_pct_beat_index"],
                "espp_pct_underwater": p["espp_pct_underwater"],
            }
        )
    return pd.DataFrame(rows)


def summary(panel: pd.DataFrame, discount: float = DEFAULT_DISCOUNT) -> dict:
    """Headline numbers for the service / widget."""
    yr = by_year(panel, discount=discount)
    pooled = pooled_distribution(panel, discount=discount)
    # average over years of the per-year stats (each year weighted equally)
    return {
        "discount": discount,
        "first_year": int(yr["year"].min()),
        "last_year": int(yr["year"].max()),
        "n_years": int(len(yr)),
        "avg_median_stock": float(yr["median_stock"].mean()),
        "avg_index_return": float(yr["index_return"].mean()),
        "avg_gap_median_minus_index": float(
            (yr["median_stock"] - yr["index_return"]).mean()
        ),
        "years_median_beat_index": int((yr["median_stock"] > yr["index_return"]).sum()),
        "median_pct_stocks_beat_index": float(yr["pct_beat_index"].median()),
        "pooled": pooled,
        "verdict": _verdict(pooled),
    }


def _verdict(pooled: dict) -> str:
    """A one-line plain-English read of whether the discount is worth the hold."""
    hs = pooled["espp_head_start"]
    gap = pooled["median_excess_vs_index"]
    beat = pooled["espp_pct_beat_index"]
    underwater = pooled["espp_pct_underwater"]
    return (
        f"A {pooled['discount']:.0%} discount is a one-time +{hs:.1%} head start. "
        f"The median single stock's one-year total return runs {gap:+.1%} vs the "
        f"index, so the discount dwarfs the typical median gap: with it, the "
        f"discounted stock beats the index in {beat:.0%} of stock-years and ends "
        f"underwater on your cash {underwater:.0%} of the time. The discount is "
        f"clearly worth taking under a one-year hold; the real cost is single-stock "
        f"downside (a fat left tail vs the diversified index), so sell and "
        f"diversify once the hold lifts rather than accumulating employer stock. "
        f"(Survivorship-biased upward — the true median is worse and the tail fatter.)"
    )
