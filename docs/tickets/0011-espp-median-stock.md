# Ticket 0011 — ESPP / median-stock analysis

**Status:** built
**Service:** `backend/app/services/espp_median_stock/` + `frontend/src/services/EsppMedianStock.jsx`
**Dataset:** `sp500_constituent_returns` (catalog.yaml)

## Question

How does an *average* stock in the S&P 500 do over a one-year holding period —
the **median** stock, not the cap-weighted index? For each of the past ~30 years,
find the median single-stock total return (dividends reinvested) and compare it to
the index. The end goal: evaluate whether an **ESPP** (employee stock purchase
plan) discount is worth it when the plan forces a one-year hold before you can
sell, leaving you exposed to a single employer stock.

## Approach

- **Universe:** current S&P 500 members (GitHub `datasets/s-and-p-500-companies`).
- **Returns:** Yahoo Finance monthly *adjusted close* (split + dividend adjusted =
  total return), compiled to Dec→Dec calendar-year total returns per stock.
- **Benchmark:** SPY (SPDR S&P 500 ETF) adjusted close — a total-return S&P 500 on
  the same Yahoo footing (Yahoo's `^SP500TR` is served too sparsely to use).
- **Median lens:** per-year cross-sectional median / mean / decile spread of
  single-stock one-year returns, % of stocks beating the index, % negative.
- **ESPP lens:** with a purchase discount `d`, the return on your cash over a
  one-year hold is `(1 + stock_return) / (1 − d) − 1`. Pooled over all stock-years
  we report: the head start the discount gives (`1/(1−d) − 1`), how often the
  discounted single stock beats the index, and how often you still end underwater
  (stock fell more than the discount). Swept over `d = 0–30%` for the widget slider.

## Findings (1994–2025, current-member universe)

- Over a **single year** the median stock tracks the index closely — the famous
  "most stocks underperform the index" result is a **long-horizon / lifetime**
  phenomenon (compounding skew), not a one-year one. Among today's members the
  median even edges the index slightly (equal- vs cap-weighting + survivorship).
- A **15% discount is a one-time ~17.6% head start** on your cash — far larger than
  the typical one-year median-stock-vs-index gap. With it, the discounted single
  stock beats the index in ~77% of stock-years, and you only end underwater (stock
  fell > 15%) ~16% of the time. **The discount is clearly worth taking under a
  one-year hold.**
- The real cost is **concentration risk**: any single stock is negative in ~30% of
  years (vs the index's far rarer down years) and the left tail is fat. So take the
  ESPP, but **sell and diversify once the hold lifts** rather than accumulating
  employer stock.

## Caveats

- **Survivorship bias** (universe = today's members) skews the median *upward*; the
  true median stock did worse and the left tail is fatter. Treat the headline as a
  survivor-friendly upper bound — it strengthens, not weakens, the "diversify after
  the hold" conclusion.
- Median/mean are effectively equal-weighted; the index is cap-weighted, so part of
  any gap is weighting, not skew. SPY carries a ~0.09%/yr expense drag.
- Dec→Dec calendar-year returns stand in for a representative one-year hold (a real
  ESPP window starts whenever you buy).

## Update — ESPP Analyzer (parameterised dashboard)

Added a second service/tab, **ESPP Analyzer** (`backend/app/services/espp_analyzer/`
+ `frontend/src/services/EsppAnalyzer.jsx`), for evaluating a *specific* plan rather
than the generic one-year case. It models full ESPP mechanics on a monthly
total-return panel (`sp500_monthly_levels`):

- **Parameters:** contribution term (3/6/12 mo), holding period after purchase
  (0/6/12/18/24 mo), lookback (on/off), discount (0–30%).
- **Average invested dollar:** contributions are spread over the term, so the
  average dollar is idle cash for `term/2` months, then buys discounted stock and is
  held `hold` months → committed `term/2 + hold` months, which is what APY annualises.
- **Lookback:** purchase price = `(1 − d) × min(start_level, purchase_level)` — captures
  both downside protection and start-price appreciation.
- **Output:** APY *spread* vs the index (ESPP APY − index APY over the same committed
  window) at the **25th / median / 75th** percentile of every (stock, start-month)
  window, plus P(beat index) and P(loss).

**What it shows:** a "garbage" plan (5%, no lookback, 12-mo term, 12-mo hold) has a
median APY spread of only ~+1.4%, beats the index just ~53% of the time, and loses
money ~24% of the time — barely better than a coin flip. **The lookback is a bigger
lever than the discount size** (5% + lookback ≫ 5% no-lookback). Short commits with a
discount annualise to very large APYs (a real one-off edge, not a repeatable rate).
