"""Pure analysis for the ESPP Analyzer.

No FastAPI, no I/O — works on the monthly total-return *levels* panel
(ticker, mkey, level, kind) and returns numbers. Pinned by tests.

ESPP mechanics modelled
-----------------------
You contribute payroll dollars over a `term` (offering period, months). At the
purchase date the accumulated cash buys stock at a discount `d`; with a
**lookback** the price is the *lower* of the start-of-offering and purchase-date
levels, then discounted. You then hold for `hold` months before selling.

Average invested dollar
-----------------------
Contributions are spread evenly across the term, so the *average* dollar is
contributed at the midpoint — it sits idle as cash for `term/2` months, then
buys stock and rides it for `hold` months. Its capital is committed for
`term/2 + hold` months, which is what we annualise over (APY). The discount has
to earn its keep against (a) that idle-cash drag and (b) just buying the index.

For an offering that starts at month `m`, using the actual share `price` (split-
but not dividend-adjusted) for the lookback and the total-return `level`
(dividends reinvested) for the holding gain:
    ref_price  = min(price(m), price(m + term)) if lookback else price(m + term)
    espp_gross = (1 / (1 - d))
               * (level(m + term + hold) / level(m + term))   # total return over hold
               * (price(m + term) / ref_price)                # lookback price edge
Using price (not total-return levels) for the lookback removes the small upward
bias from counting offering-period dividends as price appreciation; without a
lookback the price term is exactly 1, so it matches the total-return calc.
The benchmark puts the same average dollar in the index over the same committed
window [m + term/2, m + term + hold]:
    index_gross = index(m + term + hold) / index(m + term/2)
Both are annualised over years = (term/2 + hold)/12, and

    APY spread = espp_apy - index_apy

is reported at the 25th / 50th / 75th percentile across every (stock, start
month) window. Survivorship caveat (see data.py): the universe is today's S&P
500 members, so these spreads are survivor-friendly upper bounds.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TERM_OPTIONS = [3, 6, 12]          # contribution / offering period, months
HOLD_OPTIONS = [0, 6, 12, 18, 24]  # holding period after purchase, months
DISCOUNTS = [round(0.01 * i, 2) for i in range(0, 31)]  # 0%..30%

DEFAULT_TERM = 6
DEFAULT_HOLD = 12
DEFAULT_DISCOUNT = 0.15
DEFAULT_LOOKBACK = True


def _continuous_index(monthly: pd.DataFrame) -> pd.Series:
    """Index (SPY) total-return level as a dense Series indexed by integer mkey.

    Reindexed to every month in range so a fractional month (term/2 for a 3-month
    term) can be geometrically interpolated. Any internal gaps are log-interpolated.
    """
    s = (
        monthly[monthly["kind"] == "index"]
        .set_index("mkey")["level"]
        .sort_index()
    )
    full = range(int(s.index.min()), int(s.index.max()) + 1)
    s = s.reindex(full)
    # interpolate in log space (geometric) so a constant-growth gap fills smoothly
    s = np.exp(np.log(s).interpolate(method="index"))
    return s


def _level_at(s: pd.Series, k: float) -> float:
    """Index level at a (possibly fractional) month `k`, geometric interpolation."""
    f = int(np.floor(k))
    c = int(np.ceil(k))
    if f not in s.index or c not in s.index:
        return float("nan")
    lf = s.loc[f]
    if f == c:
        return float(lf)
    lc = s.loc[c]
    frac = k - f
    return float(lf * (lc / lf) ** frac)


def window_arrays(monthly: pd.DataFrame, term: int, hold: int, lookback: bool):
    """Per (stock, start-month) base ESPP multiple, index gross, and committed years.

    The gross multiple on contributed cash decomposes as

        M = (1/(1-d)) * (adj_sale / adj_purchase) * (P_purchase / ref_price)

    where the holding gain uses the total-return level (`level`, dividends
    reinvested) and the lookback edge uses the actual share `price` (split- but
    not dividend-adjusted): ref_price = min(P_start, P_purchase) if lookback else
    P_purchase. Returns (base_mult, index_gross, years) with base_mult excluding
    the 1/(1-d) discount (applied later) so a discount sweep is cheap; years is a
    scalar. Without lookback the price term is exactly 1.
    """
    stocks = monthly[monthly["kind"] == "stock"][["ticker", "mkey", "level", "price"]]
    idx = _continuous_index(monthly)
    years = (term / 2.0 + hold) / 12.0

    start = stocks.rename(columns={"price": "P_start"})[["ticker", "mkey", "P_start"]]
    pur = stocks.rename(columns={"price": "P_purchase", "level": "adj_purchase"}).copy()
    pur["mkey"] = pur["mkey"] - term  # join onto offering start month m
    sale = stocks.rename(columns={"level": "adj_sale"}).copy()
    sale["mkey"] = sale["mkey"] - (term + hold)

    df = start.merge(pur[["ticker", "mkey", "P_purchase", "adj_purchase"]], on=["ticker", "mkey"])
    df = df.merge(sale[["ticker", "mkey", "adj_sale"]], on=["ticker", "mkey"])
    df = df[
        (df["P_start"] > 0) & (df["P_purchase"] > 0)
        & (df["adj_purchase"] > 0) & (df["adj_sale"] > 0)
    ]

    # index gross over the average dollar's committed window, per unique start month
    starts = np.sort(df["mkey"].unique())
    igross = {
        int(m): _level_at(idx, m + term + hold) / _level_at(idx, m + term / 2.0)
        for m in starts
    }
    df["index_gross"] = df["mkey"].map(igross)
    df = df[np.isfinite(df["index_gross"]) & (df["index_gross"] > 0)]

    ref_price = (
        np.minimum(df["P_start"], df["P_purchase"]) if lookback else df["P_purchase"]
    )
    holding = df["adj_sale"] / df["adj_purchase"]      # total return over the hold
    lookback_edge = df["P_purchase"] / ref_price       # price appreciation captured at entry
    base_mult = (holding * lookback_edge).to_numpy()
    return base_mult, df["index_gross"].to_numpy(), years


def _pctiles(a: np.ndarray) -> dict:
    return {
        "p25": float(np.percentile(a, 25)),
        "median": float(np.percentile(a, 50)),
        "p75": float(np.percentile(a, 75)),
    }


def summarize(base_mult, index_gross, years, discount: float) -> dict:
    """APY + raw (cumulative) return percentiles for ESPP, index, and the spread.

    "Raw" returns are the total return over the committed window (not annualised);
    APY annualises the same gross multiple over `years`.
    """
    espp_gross = base_mult / (1.0 - discount)
    espp_apy = espp_gross ** (1.0 / years) - 1.0
    index_apy = index_gross ** (1.0 / years) - 1.0
    espp_raw = espp_gross - 1.0
    index_raw = index_gross - 1.0
    return {
        "n_samples": int(base_mult.size),
        "years_committed": round(float(years), 4),
        "espp_head_start": round(1.0 / (1.0 - discount) - 1.0, 6),
        # annualised (APY)
        "spread_apy": _pctiles(espp_apy - index_apy),
        "espp_apy": _pctiles(espp_apy),
        "index_apy": _pctiles(index_apy),
        # raw cumulative return over the committed window
        "spread_return": _pctiles(espp_raw - index_raw),
        "espp_return": _pctiles(espp_raw),
        "index_return": _pctiles(index_raw),
        "prob_beat_index": float(np.mean(espp_apy > index_apy)),
        "prob_loss": float(np.mean(espp_apy < 0.0)),
    }


def analyze(
    monthly: pd.DataFrame,
    term: int = DEFAULT_TERM,
    hold: int = DEFAULT_HOLD,
    lookback: bool = DEFAULT_LOOKBACK,
    discount: float = DEFAULT_DISCOUNT,
) -> dict:
    """Full ESPP-Analyzer result for one parameter set."""
    base_mult, index_gross, years = window_arrays(monthly, term, hold, lookback)
    out = summarize(base_mult, index_gross, years, discount)
    out.update(
        {"term": term, "hold": hold, "lookback": bool(lookback), "discount": discount}
    )
    return out


def grid(monthly: pd.DataFrame) -> dict:
    """Precompute every (term, hold, lookback, discount) cell for the static widget.

    Keyed "term|hold|lookback|discountpct" so the widget reads a cell directly from
    its four controls. window_arrays is computed once per (term, hold, lookback);
    the discount sweep is a cheap analytic rescale on top.
    """
    cells: dict[str, dict] = {}
    for term in TERM_OPTIONS:
        for hold in HOLD_OPTIONS:
            for lookback in (True, False):
                base_mult, index_gross, years = window_arrays(
                    monthly, term, hold, lookback
                )
                for d in DISCOUNTS:
                    key = f"{term}|{hold}|{int(lookback)}|{int(round(d * 100))}"
                    cells[key] = summarize(base_mult, index_gross, years, d)
    return cells
