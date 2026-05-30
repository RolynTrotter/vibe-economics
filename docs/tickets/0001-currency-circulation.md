# Ticket 0001 — Currency circulation crossover

**Status:** planned
**Service id:** `currency_circulation`

## Summary
When did the US dollar overtake the British pound as the world's most "circulated"
currency — and how does the answer change by metric? "Most circulated" is
ambiguous, so the service makes the metric explicit and shows the crossover under
each one.

## Questions it answers
- When did USD pass GBP as the leading **reserve** currency?
- ... as the leading **trade-invoicing / payments** currency?
- ... by **FX turnover** (most-traded)?
- How do these crossover dates differ, and why?

## Data sources (see docs/datasets.md)
- IMF **COFER** — currency composition of official FX reserves (modern).
- BIS **Triennial Survey** — FX turnover by currency (most-traded).
- SWIFT/payments shares (⚠️ partly proprietary) — invoicing/payments.
- Historical (pre-1945) sterling-vs-dollar reserve & trade-finance data — largely
  from academic series (e.g. Eichengreen/Chiţu/Mehl) which may need manual
  compilation into a small committed CSV. Document provenance carefully.

## Backend
- `model.py`: align each metric's time series, find the year USD share first
  exceeds GBP share per metric.
- Endpoints: `GET /api/currency-circulation/series?metric=reserves|turnover|payments`
  and `GET /api/currency-circulation/crossovers`.

## Frontend
- Multi-line chart: USD vs GBP share over time, metric toggle.
- "Crossover" callout cards per metric (year + one-line caveat).

## Acceptance criteria
- At least 2 metrics with real data and an explicit crossover year each.
- Caveats about metric definitions surfaced in the UI.

## Notes / risks
- Pre-WWII data is sparse and definition-dependent; be explicit about sources and
  uncertainty. This ticket leans on the acquire skill to compile a small curated
  historical CSV rather than a single live API.
