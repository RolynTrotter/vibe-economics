# Ticket 0002 — Subnational GDP comparison

**Status:** BUILT (nominal / PPP / per-capita). Median-income basis in
[ticket 0007](0007-subnational-median-income-basis.md); metro punch-out in
[ticket 0008](0008-metro-punchout-hinterlands.md); **same-year alignment + year slider
in [ticket 0009](0009-gdp-year-smoothing.md)** (the ladder is now as-of a chosen year,
1997→2025, with interpolated/cast-forward figures asterisked).
**Service id:** `subnational_gdp`

## What shipped
- Backend `app/services/subnational_gdp/` (data.py acquire+compile, pure model.py,
  router.py, tests) on **BEA Regional** (US state GDP; population derived from
  personal income ÷ per-capita income) + **World Bank WDI** (country GDP, GDP PPP,
  population). Shared `app/core/geo.py` (entity ids, parent-nation) added.
- Three bases: `nominal`, `ppp`, `per_capita` (PPP). PPP for US states uses nominal
  USD as a proxy (US ≈ PPP base; caveat surfaced).
- Widget `frontend/src/services/SubnationalGdp.jsx`: one ranked ladder of all 50
  states + DC among ~210 countries, plus a "your state ≈ which country?" matcher.
  Switching basis **FLIP-animates** each place to its new rank. US states are a
  light-blue bloc; countries are coloured by World Bank region.
- Static snapshot at `frontend/public/data/subnational_gdp.json`; the JS model is a
  1:1 port of the tested Python model (verified to match).
- Rebuild: `python -m app.services.subnational_gdp.data build` then
  `python scripts/export_static_data.py`.

## Summary
Compare the economies of subnational regions (e.g. US states) against countries
(e.g. European nations) on a like-for-like basis — nominal, PPP, per-capita, and
by median income.

## Questions it answers
- How does the GDP of California / Texas / Virginia compare to European countries?
- Same comparison by **PPP** (purchasing-power parity), not just nominal USD.
- Same by **per-capita** and by **median household income**.
- Rankings: "this US state ≈ that country".

## Data sources (see docs/datasets.md)
- **BEA Regional** (key) — US state/county GDP & personal income.
- **World Bank WDI** (key-free) — country GDP, GDP PPP, population.
- **IMF DataMapper** (key-free) — GDP USD/PPP.
- **Eurostat** (key-free) — EU regional GDP, GDP/capita PPS.
- PPP conversion factors from World Bank/OECD for apples-to-apples.

## Backend
- Shared **geographic entity** handling (state/region/country → dataset keys) —
  first consumer of what may later become `app/core/geo.py`.
- `model.py`: normalize to a common currency/year/basis (nominal | ppp |
  per_capita | median_income); compute comparisons & nearest-country matches.
- Endpoints: `GET /api/subnational-gdp/compare?entities=US-CA,DE,FR&basis=ppp`,
  `GET /api/subnational-gdp/rank?entity=US-VA&basis=ppp`.

## Frontend
- Sortable bar chart of selected entities on a chosen basis.
- "Your state ≈ country" matcher with a basis toggle (nominal/PPP/per-capita/median).
- Entity picker (states + countries).

## Acceptance criteria
- Compare ≥1 US state to ≥1 European country on ≥2 bases with real data.
- PPP vs nominal toggle visibly changes results.

## Notes / risks
- Year alignment across sources (BEA vs WB vs Eurostat release lags).
- Median income ≠ GDP/capita — keep the distinction explicit in the UI.
