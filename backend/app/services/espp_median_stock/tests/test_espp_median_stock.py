"""Tests for the ESPP / median-stock model.

Pin the cross-sectional median, the ESPP discount arithmetic, and the pooled
distribution on a small synthetic panel, plus sanity bands on the real data.
"""
import numpy as np
import pandas as pd
import pytest

from app.services.espp_median_stock import model


def _panel(stock_returns_by_year: dict[int, list[float]], index_by_year: dict[int, float]):
    """Build a tidy panel from {year: [stock returns]} and {year: index return}."""
    rows = []
    for y, rets in stock_returns_by_year.items():
        for i, r in enumerate(rets):
            rows.append({"ticker": f"T{i}", "year": y, "total_return": r, "kind": "stock"})
    for y, r in index_by_year.items():
        rows.append({"ticker": "SPY", "year": y, "total_return": r, "kind": "index"})
    return pd.DataFrame(rows)


def _wide_year(median_target: float, n: int = 40, spread: float = 0.5):
    """n returns centered so their median is exactly `median_target`."""
    offs = np.linspace(-spread, spread, n)
    offs -= np.median(offs)  # median offset 0
    return list(median_target + offs)


def test_by_year_median_and_beat():
    # Year 2000: median stock return 0.10, index 0.05 -> median beats, ~half beat index.
    panel = _panel({2000: _wide_year(0.10, n=41)}, {2000: 0.05})
    df = model.by_year(panel)
    row = df[df.year == 2000].iloc[0]
    assert row["median_stock"] == pytest.approx(0.10, abs=1e-9)
    assert row["index_return"] == pytest.approx(0.05)
    assert row["pct_beat_index"] > 0.5  # median (0.10) > index (0.05)


def test_espp_discount_arithmetic():
    # A flat stock-year of 0% with a 15% discount returns 1/0.85 - 1 on the cash.
    panel = _panel({2010: [0.0] * 40}, {2010: 0.20})
    p = model.pooled_distribution(panel, discount=0.15)
    assert p["espp_head_start"] == pytest.approx(1 / 0.85 - 1, rel=1e-9)
    assert p["espp_median_return"] == pytest.approx(1 / 0.85 - 1, rel=1e-9)
    # Stock flat -> never negative -> never underwater even though it lags the index.
    assert p["espp_pct_underwater"] == pytest.approx(0.0)
    assert p["pct_beat_index"] == pytest.approx(0.0)  # 0% < 20% index


def test_underwater_threshold_is_minus_discount():
    # Half the stocks at -0.20 (below -15% discount), half at +0.20.
    panel = _panel({2010: [-0.20] * 20 + [0.20] * 20}, {2010: 0.10})
    p = model.pooled_distribution(panel, discount=0.15)
    # espp = (1+r)/0.85 - 1; underwater iff r < -0.15 -> exactly the -0.20 half.
    assert p["espp_pct_underwater"] == pytest.approx(0.5)
    assert p["pct_loss_gt_discount"] == pytest.approx(0.5)


def test_zero_discount_is_plain_stock():
    panel = _panel({2010: _wide_year(0.07, n=41)}, {2010: 0.07})
    p = model.pooled_distribution(panel, discount=0.0)
    assert p["espp_median_return"] == pytest.approx(p["stock_median"], abs=1e-12)
    assert p["espp_head_start"] == pytest.approx(0.0)


def test_min_stocks_filter():
    # A year with too few stocks is excluded from available_years.
    panel = _panel({2010: [0.1] * 5, 2011: [0.1] * 40}, {2010: 0.05, 2011: 0.05})
    assert model.available_years(panel) == [2011]


def _has_real_data() -> bool:
    try:
        from app.services.espp_median_stock.data import load_panel

        load_panel()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_real_data(), reason="processed dataset not built")
def test_real_data_sanity():
    from app.services.espp_median_stock.data import load_panel

    panel = load_panel()
    assert {"ticker", "year", "total_return", "kind"}.issubset(panel.columns)
    s = model.summary(panel)
    # ~30 years of usable cross-sections.
    assert s["n_years"] >= 20
    # A 15% discount is a one-time head start near 17.6%.
    assert s["pooled"]["espp_head_start"] == pytest.approx(1 / 0.85 - 1, rel=1e-6)
    # With the discount, the discounted single stock beats the index most of the time.
    assert s["pooled"]["espp_pct_beat_index"] > 0.5
    # Single-stock years are negative a meaningful but minority share of the time.
    assert 0.15 < s["pooled"]["pct_negative"] < 0.45
