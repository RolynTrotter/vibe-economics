# Ticket 0007 — Subnational comparison: median-income basis

**Status:** planned (blocked on data access)
**Service id:** `subnational_gdp` (extends the built service)
**Depends on:** [0006 — data-access wishlist](0006-data-access-wishlist.md) — specifically a
**working `CENSUS_API_KEY`** (the env var currently exists but is blank) plus Eurostat
median-income coverage.

## Summary
Ticket 0002 shipped with three bases — **nominal**, **PPP**, and **GDP per capita
(PPP)**. Its fourth listed basis, **median household income**, was deliberately
deferred: it can't be built cleanly from the sources wired today. This ticket adds
it once the data access lands.

## Why it was held
GDP per capita ≠ typical household income — they diverge a lot (DC and Ireland are
the clearest cases: huge GDP/capita, far more modest median household income). Doing
median income *right* needs different sources than GDP:

- **US states:** Census **ACS** median household income (`B19013_001E`). Needs a live
  `CENSUS_API_KEY`. As of this writing the `CENSUS_API_KEY` env var is **present but
  empty**, so the acquire path can't authenticate (see 0006 §A — it's listed as
  "being provisioned").
- **Countries:** no single clean key-free median-household-income series exists.
  Candidates: Eurostat `ilc_di03` (median equivalised net income, EU only),
  OECD IDD, World Bank median consumption (LIS-derived, sparse). Coverage and
  definitions differ (household vs equivalised; income vs consumption; gross vs net).

## Scope when unblocked
- Add `median_income` to `BASES` in `model.py` / `subnationalGdpModel.js`.
- `data.py`: pull ACS median household income for states (Census) and the best
  available country series (Eurostat first, then OECD), into new columns
  `median_hh_income_usd` (+ the source/definition per entity).
- Currency-normalise country figures to USD (and offer a PPP-adjusted variant).
- UI: the basis already animates; just add the toggle option. **Surface the
  definitional caveat prominently** — median income and GDP/capita rankings will
  differ, and country median definitions are not uniform.

## Acceptance criteria
- `CENSUS_API_KEY` resolves and ACS median income fetches for all 50 states + DC.
- ≥1 country source wired with its definition recorded per entity.
- `median_income` basis selectable in the widget; the ladder reshuffles vs the GDP
  bases; caveats visible.

## Notes / risks
- Keep median income visually and textually distinct from GDP/capita so users don't
  conflate "output per person" with "what a typical household earns".
- Definitional heterogeneity across country sources is the main methodological risk;
  prefer one consistent source per region and label the rest.
