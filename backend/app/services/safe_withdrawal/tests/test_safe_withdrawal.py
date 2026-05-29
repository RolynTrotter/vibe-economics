"""Tests for the safe-withdrawal model.

Headline invariant: withdrawing the computed SWR (the upper bound) depletes the
portfolio to exactly $0 at the horizon. Plus sanity ranges on historical results.
"""
import numpy as np
import pandas as pd
import pytest

from app.services.safe_withdrawal import model
from app.services.safe_withdrawal.data import bond_year_return


def _synthetic_returns(rate=0.05, years=range(2000, 2040)):
    """Constant-real-return world: nominal = rate, zero inflation."""
    n = len(list(years))
    return pd.DataFrame(
        {
            "year": list(years),
            "stock_return": [rate] * n,
            "bond_return": [rate] * n,
            "inflation": [0.0] * n,
        }
    )


def test_max_swr_depletes_to_zero():
    """Withdrawing the SWR must land the portfolio at ~$0 at the horizon."""
    df = _synthetic_returns(rate=0.05)
    horizon = 30
    swr = model.swr_by_start_year(df, horizon, stock_weight=0.6).iloc[0]["swr"]
    path = model.portfolio_path(df, 2000, horizon, stock_weight=0.6, rate=swr)
    assert path["balance_end"].iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_swr_above_return_in_depleting_world():
    """With 5% constant real growth over 30y, the SWR exceeds 5% (you spend principal)."""
    df = _synthetic_returns(rate=0.05)
    swr = model.swr_by_start_year(df, 30, stock_weight=1.0).iloc[0]["swr"]
    assert 0.05 < swr < 0.09


def test_zero_return_world_is_one_over_horizon():
    """With 0% real return, you can withdraw exactly 1/horizon each year."""
    swr = model.max_swr_for_window(np.zeros(25))
    assert swr == pytest.approx(1.0 / 25, rel=1e-9)


def test_bond_par_when_yield_unchanged():
    """An unchanged yield gives a total return equal to the coupon (the yield)."""
    assert bond_year_return(0.04, 0.04) == pytest.approx(0.04, abs=1e-9)
    assert bond_year_return(0.04, 0.02) > 0.04  # falling yields -> capital gain


def _has_real_data() -> bool:
    try:
        from app.services.safe_withdrawal.data import load_returns

        load_returns()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_real_data(), reason="processed dataset not built")
def test_real_data_sanity():
    """On real Shiller data, 30y/60-40 worst-case upper bound sits in a plausible band."""
    from app.services.safe_withdrawal.data import load_returns

    df = load_returns()
    s = model.summary(df, horizon=30, stock_weight=0.6)
    # Historical worst 30-year SWR for a balanced portfolio is roughly 3.5-4.5%.
    assert 0.025 < s["min_swr"] < 0.055
    assert s["median_swr"] > 0.045          # median safe rate comfortably above 4%
    assert 1955 <= s["min_swr_start_year"] <= 1975  # worst cohorts ~ late 60s/early 70s
