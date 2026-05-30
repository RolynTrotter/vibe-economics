# Ticket 0003 — Safe withdrawal backtester  ⭐ reference service

**Status:** BUILT (this is the reference template for all other services)
**Service id:** `safe_withdrawal`

## Summary
We know the "4% rule". For each retirement **start year** in the historical
record, what was the *maximum constant inflation-adjusted withdrawal rate* that
brought a portfolio to **exactly $0** at the end of a 30-year retirement — under
different allocations?

## Questions it answers
- For a retirement starting in year Y, what withdrawal rate exactly depletes the
  portfolio over a 30-year horizon? (the "perfect-hindsight" SWR)
- How does that differ for **all-US-stock**, **60/40**, and a **three-fund /
  Boglehead** allocation?
- How does the safe rate vary across start years (sequence-of-returns risk)?
- What's the worst-case / historical-minimum safe rate? (the empirical "X% rule")

## Data
- **`shiller_returns`** — Shiller `ie_data.xls` → `data/processed/shiller_returns.parquet`
  with annual `stock_return`, `bond_return`, `inflation` (real returns derived).
- Allocations modelled as weighted blends of the stock & bond series (the
  three-fund's intl/bond split is approximated with the available series; noted in UI).

## Backend (`backend/app/services/safe_withdrawal/`)
- `data.py` — `compile_shiller()` + cached loader.
- `model.py` (pure):
  - `max_safe_withdrawal_rate(returns, start_year, horizon, weights)` — binary
    search / closed-form for the rate that lands at ~$0.
  - `swr_by_start_year(returns, horizon, weights)` — series across all start years.
  - `portfolio_path(returns, start_year, horizon, weights, rate)` — balance path.
- `router.py` — `GET /api/safe-withdrawal/by-year`, `/path`, `/summary`.
- `tests/test_safe_withdrawal.py` — pins known numeric results.

## Frontend (`frontend/src/services/SafeWithdrawal.jsx`)
- Allocation preset (all-stock / 60-40 / three-fund) + weight sliders.
- Horizon control (default 30y).
- Line chart: safe withdrawal rate by start year (reusing `LineChart`).
- Result cards: historical-minimum safe rate, median, the 4%-rule comparison.

## Acceptance criteria — all met
- Endpoint returns SWR by start year for the three allocations.
- A pinned test verifies the depletion math (portfolio ends ≈ $0 at the computed rate).
- Widget renders on a phone, controls update the chart.

## Why this is the template
Cleanest full pipeline on authoritative, key-free, ToS-clean data; pure tested
model; interactive widget. Copy its structure for every other service.
