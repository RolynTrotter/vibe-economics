# Ticket 0009 — Same-year alignment + year slider for the GDP/income ladder

**Status:** BUILT.
**Service id:** `subnational_gdp` (extends ticket 0002; new dataset
`subnational_gdp_timeseries`).

## Summary
The ladder (ticket 0002) compared US states to countries on whichever year each
source had last published — BEA states ran a year (or two) ahead of World Bank
countries, and the median-income basis lagged further still. This ticket makes the
comparison **as-of one chosen year**, exposed as a **slider** (1997 → latest), and
fills the gaps each source leaves with interpolation / short-horizon extrapolation,
**flagging every imputed figure with an asterisk (\*)**. The terminal year is the
latest year any source has an actual (currently 2025, thanks to BEA's preliminary
state figure and IMF WEO's current-year estimates).

## What shipped
- **New dataset `subnational_gdp_timeseries`** (`backend/.../timeseries.py`): a long,
  tidy multi-year series `entity_id | name | kind | parent | region | year | metric |
  value | source`, with `metric ∈ {gdp_nominal_usd, gdp_ppp_usd, population}` and
  `source ∈ {bea, worldbank, imf}`.
  - **BEA Regional** SAGDP2 (current-dollar state GDP, 1997+) + SASUMMARY personal
    income / per-capita income (state population per year). Public domain.
  - **World Bank WDI** full history of nominal GDP, PPP GDP, population. CC BY 4.0.
  - **IMF DataMapper / WEO** (NGDPD, PPPGDP, LP) — observations *and* near-term
    forecasts, used **only as a growth signal**, never spliced as a level. IMF terms.
- **Estimator** (`backend/.../estimate.py`): `entities_for_year(ts, year, median_df)`
  returns the wide one-row-per-place table the model/UI already consume, every place
  on `year`, with per-field `*_estimated` flags and the anchor year used.
- **Model** (`model.py`): `basis_estimated()` maps the per-field flags onto each basis;
  `ranked_table()` / `nearest()` now carry an `estimated` column.
- **Router**: `year` query param on `/ranking`, `/compare`, `/rank`; `/meta` reports the
  available `{min, max, default}` years. Omitting `year` keeps the original
  latest-snapshot behaviour (back-compat).
- **Static export**: `subnational_gdp.json` now ships `years` + `by_year` (a precomputed,
  flagged table per year, 1997–latest). The widget slices by year client-side; the JS
  model (`subnationalGdpModel.js`) mirrors `basis_estimated` so deployed numbers equal
  the tested backend. ~2 MB raw / ~0.35 MB gzipped.
- **Widget** (`SubnationalGdp.jsx`): a year slider, an asterisk + muted styling on every
  estimated figure (ladder and the "your state ≈ which country?" matcher), a live
  "N of M shown are estimated" readout, and a short explanation under the table plus a
  full methodology note. The slider is disabled under metro punch-out (the hinterland
  view stays on its latest vintage; out of scope here).
- **Tests** (`tests/test_estimate.py`): the interpolation/extrapolation/eligibility rules
  pinned on synthetic series, plus integration checks against the built parquet.

Rebuild: `python -m app.services.subnational_gdp.timeseries build` then
`python scripts/export_static_data.py`.

## Method (the interesting part)

For each place and each metric (nominal GDP, PPP GDP, population) **independently**,
given a target year `Y`, let the *actuals* be the observed BEA/World Bank values:

1. **Exact** — `Y` is observed → use it (not flagged).
2. **Interpolate** — `Y` lies between two actuals → **log-linear** interpolation
   (constant growth between the brackets), flagged `*`. This is the easy "2023 from
   2022 & 2024" case the ticket called out.
3. **Extrapolate forward** — `Y` is at most `FORWARD_HORIZON = 2` years past the last
   actual → grow the last actual by **IMF WEO year-on-year growth** when the IMF covers
   both endpoints (so a country whose World Bank GDP stops at 2024 is carried to 2025 on
   the IMF's 2024→2025 path), else by the place's own recent CAGR. Flagged `*`. Using the
   IMF *ratio* rather than its *level* keeps the series internally consistent (World
   Bank levels throughout) while borrowing the IMF's near-term shape.
4. **Extrapolate back** — symmetric, ≤ `BACK_HORIZON = 2` years before the first actual.
5. Otherwise **no value**.

**Per-capita** is `PPP ÷ population`, each estimated independently, and is flagged if
either input was. **Median income** (sparse, its own vintage per country) is carried to
`Y` by **PPP-per-capita growth** between its vintage year and `Y`, flagged whenever
`Y ≠ vintage`.

**Eligibility falls out of the horizons.** If *every* metric for a place stops more than
two years before `Y`, every metric returns "no value" and the place simply drops out for
that year — we do not presume where an economy ended up when nobody (not even the IMF)
has data near it. But a place is included on whatever bases it *can* support: this is
exactly the ticket's example — 2025 nominal GDP + 2024 population + a 2023 metro/median
assembles into a 2025 row (population and median flagged), while a country last seen in
2021 shows nothing at 2025.

### The harder cross-metric cast-forward
The ticket flagged the tricky case: a figure exists for 2023 and *different* metrics for
2025. Because each metric is estimated independently against its own actuals + IMF growth,
this composes naturally — e.g. PPP-per-capita at 2025 uses PPP carried 2024→2025 (IMF) over
population carried 2024→2025 (IMF), and the 2023 median is scaled onto it by the
2023→2025 PPP-per-capita growth. Each leg is flagged; the composite reads `*`.

## Decisions & limits (deliberate)
- **Floor at 1997.** BEA's current-dollar state GDP (SAGDP2) starts in 1997, so a
  *states-and-countries* ladder is only complete from then. Countries alone could go
  back to 1960 (World Bank) / 1980 (IMF); kept to 1997 for one comparable range. Easy to
  extend the floor later (it's `START_YEAR` in `timeseries.py`).
- **Horizon = 2 years.** Long enough to reach 2025 from 2023 actuals; short enough that
  "estimates" stay close to real observations. Past that we drop rather than guess.
- **IMF as growth only.** Avoids level discontinuities where the IMF and World Bank
  disagree on a country's absolute GDP.
- **Median income** is a coarse cast-forward (one growth proxy, PPP-per-capita); its
  underlying coverage (OECD/EU + US) is unchanged from ticket 0007.
- **Metro punch-out (hinterland, ticket 0008)** is *not* year-aware here; it keeps its
  latest-vintage snapshot and the slider is disabled when it's on.

## Acceptance criteria
- A slider aligns every place to a chosen year back to ~2000 (here 1997), terminating at
  2025. ✓
- Interpolated and forward-cast figures are asterisked; methodology is documented in this
  ticket and summarised under the table. ✓
- Places with no data near a recent year are dropped, not invented. ✓
