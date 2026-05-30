"""Tests for the safe-withdrawal model.

Headline invariant: withdrawing the computed SWR (the upper bound) depletes the
portfolio to exactly $0 at the horizon. Plus sanity ranges on historical results
and a check that the real international sleeve makes the three-fund differ from 60/40.
"""
import numpy as np
import pandas as pd
import pytest

from app.services.safe_withdrawal import model
from app.services.safe_withdrawal.data import bond_year_return, _usd_return


def _synthetic_returns(rate=0.05, years=range(2000, 2040)):
    """Constant-real-return world: nominal = rate everywhere, zero inflation."""
    n = len(list(years))
    return pd.DataFrame(
        {
            "year": list(years),
            "us_stock": [rate] * n,
            "intl_stock": [rate] * n,
            "bond": [rate] * n,
            "inflation": [0.0] * n,
        }
    )


def test_max_swr_depletes_to_zero():
    """Withdrawing the SWR must land the portfolio at ~$0 at the horizon."""
    df = _synthetic_returns(rate=0.05)
    horizon = 30
    w = model.PRESETS["sixty_forty"]
    swr = model.swr_by_start_year(df, horizon, w).iloc[0]["swr"]
    path = model.portfolio_path(df, 2000, horizon, w, rate=swr)
    assert path["balance_end"].iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_swr_above_return_in_depleting_world():
    """With 5% constant real growth over 30y, the SWR exceeds 5% (you spend principal)."""
    df = _synthetic_returns(rate=0.05)
    swr = model.swr_by_start_year(df, 30, model.PRESETS["all_stock"]).iloc[0]["swr"]
    assert 0.05 < swr < 0.09


def test_zero_return_world_is_one_over_horizon():
    """With 0% real return, you can withdraw exactly 1/horizon each year."""
    swr = model.max_swr_for_window(np.zeros(25))
    assert swr == pytest.approx(1.0 / 25, rel=1e-9)


def test_weights_normalize_and_validate():
    w = model.normalize_weights({"us": 0.36, "intl": 0.24, "bond": 0.40})
    assert sum(w.values()) == pytest.approx(1.0)
    # Unnormalized input is renormalized.
    w2 = model.normalize_weights({"us": 2.0, "bond": 2.0})
    assert w2["us"] == pytest.approx(0.5) and w2["bond"] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        model.normalize_weights({"us": -0.1, "bond": 1.1})


def test_usd_conversion():
    """Local return + currency move composes into the USD return."""
    # Flat FX -> USD return equals local return.
    assert _usd_return(0.10, 1.5, 1.5) == pytest.approx(0.10)
    # Foreign currency strengthens (xrusd 1.5 -> 1.0): USD return beats local.
    assert _usd_return(0.0, 1.5, 1.0) == pytest.approx(0.5)


def test_bond_par_when_yield_unchanged():
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
    """On real JST data, the 60/40 worst-case upper bound sits in a plausible band."""
    from app.services.safe_withdrawal.data import load_returns

    df = load_returns()
    assert {"us_stock", "intl_stock", "bond", "inflation"}.issubset(df.columns)
    s = model.summary(df, horizon=30, weights=model.PRESETS["sixty_forty"])
    assert 0.02 < s["min_swr"] < 0.06
    assert s["median_swr"] > 0.04


@pytest.mark.skipif(not _has_real_data(), reason="processed dataset not built")
def test_three_fund_differs_from_sixty_forty():
    """The real international sleeve must make the 3-fund diverge from US 60/40."""
    from app.services.safe_withdrawal.data import load_returns

    df = load_returns()
    tf = model.summary(df, 30, model.PRESETS["three_fund"])
    sf = model.summary(df, 30, model.PRESETS["sixty_forty"])
    # Same equity/bond ratio, different equity composition -> results must differ.
    assert tf["min_swr"] != pytest.approx(sf["min_swr"], abs=1e-4)
