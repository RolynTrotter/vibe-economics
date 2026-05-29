# Ticket 0005 — Cost of living comparison  ⭐ flagship

**Status:** planned (next to build — acquisition skill scaffolded)
**Service id:** `cost_of_living`

## Summary
Compare cost of living between two places across metrics like rent, groceries,
healthcare, transport, and utilities — and express the result as the relative
savings (or premium) of moving from one to the other. Designed around the
flagship conversational user story:

> "Compare cost of living between Northern Virginia (outside DC) and Johor Bahru,
> Malaysia (outside Singapore). Across rent, groceries, and healthcare, show the
> relative savings from these different jumps in polity within one metro area.
> Find and grab the datasets, produce a report, and make widgets I can verify."

## Questions it answers
- Category-by-category cost ratio between two places (rent, groceries, healthcare,
  transport, utilities).
- Overall basket-weighted cost-of-living index difference.
- "Center vs satellite" framing: cost of the core metro vs its cheaper neighbor
  (DC vs NoVA; Singapore vs Johor Bahru), and the savings from each jump.
- Adjusted for local income / PPP where the question is about real affordability.

## Data sources (see docs/datasets.md) — license matters here
Prefer official, license-clean sources; treat city-aggregators carefully.
- **OECD comparative price levels** (key-free) and **Eurostat price levels** —
  clean country-level baselines.
- **BEA Regional Price Parities** (US, free key) — license-clean US metro-level
  price differences (great for the NoVA/DC side).
- National statistics offices (e.g. Malaysia DOSM) for the SG/JB side.
- ⚠️ **Numbeo** — richest city-level rent/grocery/healthcare detail but
  **proprietary / paid API / ToS-restricted**. Use only with a valid
  `NUMBEO_API_KEY` and within terms; prefer official substitutes; always cite and
  flag in the report when used.

This ticket is the **hardest exercise of the acquire/compile skills**: multiple
sources, geographic entity resolution (metro ↔ city ↔ country), differing
currencies and base years, and a license-sensitive source. That's deliberate —
it's the proving ground after the reference service.

## Backend
- Reuse/extend the geo entity handling from ticket 0002 (`app/core/geo.py`).
- `data.py` — compile each source into tidy `place, category, item, price, currency, year`.
- `model.py` — normalize currencies (FX/PPP), build category ratios and a
  basket-weighted index between two places; optional income-adjustment.
- Endpoints: `GET /api/cost-of-living/compare?from=US-NoVA&to=MY-JB&categories=rent,groceries,healthcare`,
  `/basket`, `/places` (search/resolve).

## Frontend
- Place pickers (with the "center vs satellite" preset framing).
- Category comparison bars (savings/premium per category).
- Overall index card + basket weighting controls.
- Source/units/caveat footnotes so findings are verifiable.

## Report
- Conversational runs emit a markdown report (savings per category, overall, with
  sources and caveats) alongside the widget.

## Acceptance criteria
- Compare two real places across ≥3 categories with sourced data.
- Currency/PPP normalization is explicit and toggleable.
- License of every source used is recorded; proprietary sources flagged in output.

## Notes / risks
- City-level granularity vs official country/metro granularity: be explicit about
  what level each number actually represents.
- Numbeo licensing — do not scrape; key + ToS only, or substitute official data.
