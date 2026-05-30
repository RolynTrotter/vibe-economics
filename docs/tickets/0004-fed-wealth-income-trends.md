# Ticket 0004 — Fed wealth & income trends

**Status:** planned
**Service id:** `fed_wealth_income`

## Summary
How have US income and wealth statistics changed over time, by group, according
to Federal Reserve data?

## Questions it answers
- How have **wealth shares** by percentile (top 1% / next 9% / next 40% / bottom 50%)
  changed over time?
- How has **median vs mean** net worth diverged?
- Income vs wealth concentration trends.
- Breakdowns by age, education, or race where available.

## Data sources (see docs/datasets.md)
- **Fed DFA** (Distributional Financial Accounts) — quarterly wealth by percentile,
  CSV, key-free. Primary (good time series).
- **Fed SCF** (Survey of Consumer Finances) — triennial, deeper demographic detail.

## Backend
- `data.py` — compile DFA CSV → tidy `quarter, group, measure, value`.
- `model.py` — shares over time, median/mean ratios, growth since a base year,
  inflation-adjust where relevant.
- Endpoints: `GET /api/fed-wealth-income/shares?measure=net_worth`,
  `/series?group=Top1&measure=...`.

## Frontend
- Stacked-area / line chart of wealth share by percentile over time.
- Median-vs-mean divergence chart.
- Group/measure selectors.

## Acceptance criteria
- Wealth-share-by-percentile time series from real DFA data.
- Real (inflation-adjusted) toggle where applicable.

## Notes / risks
- DFA and SCF use different methodologies — don't mix series without noting it.
- Be careful with nominal vs real comparisons across decades.
