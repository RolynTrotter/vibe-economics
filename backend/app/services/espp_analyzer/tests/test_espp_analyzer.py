"""Tests for the ESPP Analyzer model.

Pin the lookback rule, the discount/annualisation arithmetic, and the
average-dollar committed horizon on tiny synthetic monthly panels.
"""
import numpy as np
import pytest

import pandas as pd

from app.services.espp_analyzer import model


def _panel(stock_levels, index_levels, stock_prices=None):
    """Build a monthly panel from {ticker: {mkey: level}} + {mkey: index level}.

    `stock_prices` (same shape) sets the split-adjusted *price* used by the
    lookback; when omitted, price = level (no dividend wedge).
    """
    rows = []
    for tk, lv in stock_levels.items():
        prices = (stock_prices or {}).get(tk, lv)
        for mkey, level in lv.items():
            y, mo = divmod(mkey, 12)
            rows.append({"ticker": tk, "mkey": mkey, "year": y, "month": mo + 1,
                         "level": float(level), "price": float(prices[mkey]), "kind": "stock"})
    for mkey, level in index_levels.items():
        y, mo = divmod(mkey, 12)
        rows.append({"ticker": "SPY", "mkey": mkey, "year": y, "month": mo + 1,
                     "level": float(level), "price": float(level), "kind": "index"})
    return pd.DataFrame(rows)


def test_no_lookback_flat_stock_is_pure_discount():
    # One stock dead flat at 100 over a 6-month term + 6-month hold; index flat too.
    base = {m: 100.0 for m in range(24000, 24020)}
    panel = _panel({"AAA": base}, {m: 100.0 for m in range(24000, 24020)})
    r = model.analyze(panel, term=6, hold=6, lookback=False, discount=0.15)
    # espp_gross = 1/0.85; committed years = (3+6)/12 = 0.75
    years = (6 / 2 + 6) / 12
    expected_apy = (1 / 0.85) ** (1 / years) - 1
    assert r["espp_apy"]["median"] == pytest.approx(expected_apy, rel=1e-9)
    # flat index -> 0% index APY -> spread == espp APY
    assert r["index_apy"]["median"] == pytest.approx(0.0, abs=1e-9)
    assert r["spread_apy"]["median"] == pytest.approx(expected_apy, rel=1e-9)
    assert r["years_committed"] == pytest.approx(0.75)


def test_lookback_protects_on_a_decline():
    # Stock falls 100 -> 80 over the term, then flat through the hold.
    # No-lookback buys at 80; lookback also buys at min(100,80)=80 -> same here,
    # but lookback must never be worse than no-lookback.
    lv = {24000: 100.0, 24006: 80.0, 24012: 80.0}
    panel = _panel({"AAA": lv}, {24000: 100.0, 24006: 100.0, 24012: 100.0})
    no_lb = model.analyze(panel, term=6, hold=6, lookback=False, discount=0.10)
    lb = model.analyze(panel, term=6, hold=6, lookback=True, discount=0.10)
    assert lb["espp_apy"]["median"] >= no_lb["espp_apy"]["median"] - 1e-12


def test_lookback_captures_appreciation():
    # Stock rises 100 -> 125 over the term, flat through hold.
    # Lookback buys at min(100,125)=100 (the lower, older price) -> you pocket the
    # 25% run-up *and* the discount; no-lookback buys at 125 -> only the discount.
    lv = {24000: 100.0, 24006: 125.0, 24012: 125.0}
    panel = _panel({"AAA": lv}, {24000: 100.0, 24006: 100.0, 24012: 100.0})
    no_lb = model.analyze(panel, term=6, hold=6, lookback=False, discount=0.10)
    lb = model.analyze(panel, term=6, hold=6, lookback=True, discount=0.10)
    years = (6 / 2 + 6) / 12
    # lookback gross = 125 / (0.9 * 100); no-lookback gross = 125 / (0.9 * 125)
    assert lb["espp_apy"]["median"] == pytest.approx((125 / 90) ** (1 / years) - 1, rel=1e-9)
    assert no_lb["espp_apy"]["median"] == pytest.approx((1 / 0.9) ** (1 / years) - 1, rel=1e-9)
    assert lb["espp_apy"]["median"] > no_lb["espp_apy"]["median"]


def test_lookback_uses_price_not_total_return():
    # Price rises 100 -> 110 over the term (10% price appreciation), but the
    # total-return level rises 100 -> 120 (extra 10 from dividends). Flat through
    # the hold. The lookback edge must follow PRICE (110/100), not the TR level
    # (120/100): gross = (level_sale/level_purchase) * (P_purchase/min(P_start,P_purchase))
    #                  = (120/120) * (110/100) = 1.10, then / (1-d).
    levels = {24000: 100.0, 24006: 120.0, 24012: 120.0}
    prices = {24000: 100.0, 24006: 110.0, 24012: 110.0}
    panel = _panel({"AAA": levels}, {24000: 100.0, 24006: 100.0, 24012: 100.0},
                   stock_prices={"AAA": prices})
    r = model.analyze(panel, term=6, hold=6, lookback=True, discount=0.10)
    years = (6 / 2 + 6) / 12
    assert r["espp_apy"]["median"] == pytest.approx((1.10 / 0.90) ** (1 / years) - 1, rel=1e-9)
    # The old total-return proxy would have given the higher 1.20/0.90 gross.
    proxy = (1.20 / 0.90) ** (1 / years) - 1
    assert r["espp_apy"]["median"] < proxy


def test_committed_horizon_scales_apy():
    # Same one-shot 10% discount edge annualises higher over a shorter commit.
    base = {m: 100.0 for m in range(24000, 24040)}
    panel = _panel({"AAA": base}, {m: 100.0 for m in range(24000, 24040)})
    short = model.analyze(panel, term=3, hold=0, lookback=False, discount=0.10)
    long = model.analyze(panel, term=12, hold=24, lookback=False, discount=0.10)
    assert short["years_committed"] == pytest.approx((3 / 2 + 0) / 12)
    assert long["years_committed"] == pytest.approx((12 / 2 + 24) / 12)
    assert short["espp_apy"]["median"] > long["espp_apy"]["median"]


def _has_real_data() -> bool:
    try:
        from app.services.espp_median_stock.data import load_monthly

        load_monthly()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_real_data(), reason="monthly dataset not built")
def test_real_data_sanity():
    from app.services.espp_median_stock.data import load_monthly

    monthly = load_monthly()
    # A garbage ESPP: 5% discount, no lookback, 12-month term, 12-month hold.
    bad = model.analyze(monthly, term=12, hold=12, lookback=False, discount=0.05)
    # A generous one: 15% discount + lookback, short term, sell at purchase.
    good = model.analyze(monthly, term=6, hold=0, lookback=True, discount=0.15)
    assert bad["n_samples"] > 1000 and good["n_samples"] > 1000
    # The generous plan's median APY spread must beat the garbage one's.
    assert good["spread_apy"]["median"] > bad["spread_apy"]["median"]
    # Percentiles must be ordered.
    for r in (bad, good):
        assert r["spread_apy"]["p25"] <= r["spread_apy"]["median"] <= r["spread_apy"]["p75"]
