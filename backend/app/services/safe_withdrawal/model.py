"""Pure analysis for the safe-withdrawal backtester.

No FastAPI, no I/O — every function takes a returns DataFrame (+ params) and
returns numbers/DataFrames. This is what the tests pin.

What it computes — the *upper bound on the 4% rule*
---------------------------------------------------
For a retirement starting in a given year, the "safe withdrawal rate" (SWR) here
is the **maximum** constant inflation-adjusted withdrawal — as a fraction of the
initial balance — that, with perfect hindsight, brings the portfolio to *exactly*
$0 at the end of the horizon. It is the best you could possibly have withdrawn
without running out: an upper bound. The 4% rule asks the inverse (does 4%
survive?); the historical **minimum** of these per-cohort upper bounds is the
empirically safe rate to compare against 4%.

Conventions
-----------
- Work in **real** (inflation-adjusted) terms. A constant real withdrawal is taken
  at the **start** of each year; the remainder grows by that year's real blended
  return. real = (1 + nominal_blend)/(1 + inflation) - 1, where
  nominal_blend = stock_weight*stock_return + (1-stock_weight)*bond_return
  (annually rebalanced).
- Balance recursion: B_t = (B_{t-1} - w)*(1 + rr_t), B_0 = 1, solve B_H = 0 for w.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# The rule of thumb we are bounding.
RULE_OF_THUMB = 0.04

# Named allocations (stock weight; bond weight = 1 - stock).
# `three_fund` approximates a Boglehead total-market 3-fund; international equity
# is proxied by US equity because the Shiller dataset is US-only (noted in UI).
PRESETS: dict[str, float] = {
    "all_stock": 1.0,
    "three_fund": 0.70,
    "sixty_forty": 0.60,
}


def real_returns(returns: pd.DataFrame, stock_weight: float) -> pd.Series:
    """Real annual blended return per year, indexed by `year`."""
    sw = float(stock_weight)
    nominal = sw * returns["stock_return"] + (1.0 - sw) * returns["bond_return"]
    real = (1.0 + nominal) / (1.0 + returns["inflation"]) - 1.0
    return pd.Series(real.values, index=returns["year"].values, name="real_return")


def max_swr_for_window(real_seq: np.ndarray) -> float:
    """Constant real withdrawal fraction that depletes the portfolio to exactly $0.

    real_seq: array of `horizon` real returns (decimals). Returns the SWR
    (fraction of the initial balance), withdrawing at the start of each year:

        w = Π(1 + r_t)  /  Σ_k Π_{t>=k}(1 + r_t)
    """
    growth = 1.0 + np.asarray(real_seq, dtype=float)
    suffix_prod = np.cumprod(growth[::-1])[::-1]  # suffix_prod[k] = prod(growth[k:])
    return float(suffix_prod[0] / suffix_prod.sum())


def swr_by_start_year(
    returns: pd.DataFrame, horizon: int, stock_weight: float
) -> pd.DataFrame:
    """SWR (the per-cohort upper bound) for every start year with a full window."""
    rr = real_returns(returns, stock_weight)
    years = rr.index.to_numpy()
    vals = rr.to_numpy()
    rows = []
    for i in range(len(years) - horizon + 1):
        rows.append((int(years[i]), max_swr_for_window(vals[i : i + horizon])))
    return pd.DataFrame(rows, columns=["start_year", "swr"])


def portfolio_path(
    returns: pd.DataFrame,
    start_year: int,
    horizon: int,
    stock_weight: float,
    rate: float,
) -> pd.DataFrame:
    """Real balance path withdrawing a constant real `rate` of the initial balance.

    Columns: year, balance_start (before withdrawal), withdrawal, balance_end
    (after growth). Balances are in units of the initial portfolio (= 1.0).
    """
    rr = real_returns(returns, stock_weight)
    years = rr.index.to_numpy()
    if start_year not in years:
        raise ValueError(f"start_year {start_year} not in data range")
    idx = int(np.where(years == start_year)[0][0])
    if idx + horizon > len(years):
        raise ValueError(
            f"Not enough data for a {horizon}-year window starting {start_year}"
        )
    balance = 1.0
    rows = []
    for h in range(horizon):
        y = int(years[idx + h])
        start_bal = balance
        balance = (balance - rate) * (1.0 + float(rr.iloc[idx + h]))
        rows.append((y, start_bal, rate, balance))
    return pd.DataFrame(
        rows, columns=["year", "balance_start", "withdrawal", "balance_end"]
    )


def summary(returns: pd.DataFrame, horizon: int, stock_weight: float) -> dict:
    """Headline stats across all start years for an allocation/horizon.

    `min_swr` is the worst historical cohort's upper bound — the empirically safe
    rate to set against the 4% rule (`baseline_4pct_rule`).
    """
    by_year = swr_by_start_year(returns, horizon, stock_weight)
    swr = by_year["swr"]
    worst_idx = int(swr.idxmin())
    return {
        "horizon": horizon,
        "stock_weight": stock_weight,
        "n_start_years": int(len(by_year)),
        "first_start_year": int(by_year["start_year"].min()),
        "last_start_year": int(by_year["start_year"].max()),
        "baseline_4pct_rule": RULE_OF_THUMB,
        "min_swr": float(swr.min()),            # worst-case upper bound = empirical safe rate
        "min_swr_start_year": int(by_year.loc[worst_idx, "start_year"]),
        "median_swr": float(swr.median()),
        "max_swr": float(swr.max()),
        "max_swr_start_year": int(by_year.loc[int(swr.idxmax()), "start_year"]),
        "share_at_least_4pct": float((swr >= RULE_OF_THUMB).mean()),
    }
