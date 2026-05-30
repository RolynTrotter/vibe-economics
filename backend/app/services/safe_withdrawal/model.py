"""Pure analysis for the safe-withdrawal backtester.

No FastAPI, no I/O — every function takes a returns DataFrame (+ params) and
returns numbers/DataFrames. This is what the tests pin.

What it computes — the *upper bound on the 4% rule*
---------------------------------------------------
For a retirement starting in a given year, the "safe withdrawal rate" (SWR) here
is the **maximum** constant inflation-adjusted withdrawal — as a fraction of the
initial balance — that, with perfect hindsight, brings the portfolio to *exactly*
$0 at the end of the horizon. It is an upper bound: the best you could possibly
have withdrawn. The historical **minimum** of these per-cohort upper bounds is the
empirically safe rate to compare against the 4% rule of thumb.

Three-asset allocations
-----------------------
Weights are a dict over {us, intl, bond} that sum to 1 (us/intl are equity sleeves,
bond is fixed income). With a *real* international sleeve in the data, a three-fund
portfolio genuinely diverges from a US 60/40. Conventions:
- Work in **real** (inflation-adjusted) terms; constant real withdrawal at the
  start of each year, remainder grows by that year's real blended return.
  nominal_blend = us*us_stock + intl*intl_stock + bond*bond  (annually rebalanced)
  real = (1 + nominal_blend) / (1 + inflation) - 1
- Balance recursion: B_t = (B_{t-1} - w)*(1 + rr_t), B_0 = 1, solve B_H = 0 for w.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# The rule of thumb we are bounding.
RULE_OF_THUMB = 0.04

# Named allocations as {us, intl, bond} weights (must sum to 1).
# - all_stock:    100% US equity (the classic "all US stock").
# - sixty_forty:  US 60 / bond 40 (no international).
# - three_fund:   same 60/40 equity/bond split, but the 60 equity is split 60/40
#                 US/international — so the ONLY difference from sixty_forty is the
#                 real international diversification. (Boglehead total-market style.)
PRESETS: dict[str, dict[str, float]] = {
    "all_stock": {"us": 1.0, "intl": 0.0, "bond": 0.0},
    "three_fund": {"us": 0.36, "intl": 0.24, "bond": 0.40},
    "sixty_forty": {"us": 0.60, "intl": 0.0, "bond": 0.40},
}

ASSETS = ("us", "intl", "bond")


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Fill missing assets with 0 and validate the weights sum to ~1."""
    w = {a: float(weights.get(a, 0.0)) for a in ASSETS}
    total = sum(w.values())
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    if any(v < 0 for v in w.values()):
        raise ValueError("weights must be non-negative")
    # Allow tiny float drift; otherwise renormalize so the blend is well-defined.
    if abs(total - 1.0) > 1e-9:
        w = {a: v / total for a, v in w.items()}
    return w


def real_returns(returns: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Real annual blended return per year, indexed by `year`."""
    w = normalize_weights(weights)
    nominal = (
        w["us"] * returns["us_stock"]
        + w["intl"] * returns["intl_stock"]
        + w["bond"] * returns["bond"]
    )
    real = (1.0 + nominal) / (1.0 + returns["inflation"]) - 1.0
    return pd.Series(real.values, index=returns["year"].values, name="real_return")


def max_swr_for_window(real_seq: np.ndarray) -> float:
    """Constant real withdrawal fraction that depletes the portfolio to exactly $0.

        w = Π(1 + r_t)  /  Σ_k Π_{t>=k}(1 + r_t)   (withdraw at start of each year)
    """
    growth = 1.0 + np.asarray(real_seq, dtype=float)
    suffix_prod = np.cumprod(growth[::-1])[::-1]  # suffix_prod[k] = prod(growth[k:])
    return float(suffix_prod[0] / suffix_prod.sum())


def swr_by_start_year(
    returns: pd.DataFrame, horizon: int, weights: dict[str, float]
) -> pd.DataFrame:
    """SWR (the per-cohort upper bound) for every start year with a full window."""
    rr = real_returns(returns, weights)
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
    weights: dict[str, float],
    rate: float,
) -> pd.DataFrame:
    """Real balance path withdrawing a constant real `rate` of the initial balance.

    Columns: year, balance_start (before withdrawal), withdrawal, balance_end
    (after growth). Balances are in units of the initial portfolio (= 1.0).
    """
    rr = real_returns(returns, weights)
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


def summary(returns: pd.DataFrame, horizon: int, weights: dict[str, float]) -> dict:
    """Headline stats across all start years for an allocation/horizon.

    `min_swr` is the worst historical cohort's upper bound — the empirically safe
    rate to set against the 4% rule (`baseline_4pct_rule`).
    """
    w = normalize_weights(weights)
    by_year = swr_by_start_year(returns, horizon, w)
    swr = by_year["swr"]
    worst_idx = int(swr.idxmin())
    return {
        "horizon": horizon,
        "weights": w,
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
