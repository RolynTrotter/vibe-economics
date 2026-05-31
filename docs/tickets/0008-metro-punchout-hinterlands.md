# Ticket 0008 — Metro punch-out / "hinterland" comparison

**Status:** Phase 1 BUILT (country-level) · Phase 2 BUILT (per-US-state, CSA county footprint).
**Service id:** `subnational_gdp` (extends it; new dataset `subnational_metros`)
**Depends on:** OECD SDMX (key-free, allowlisted) + World Bank WDI.

## The question
National GDP-per-capita is propped up by one or two global cities. London is **28%**
of UK GDP, Paris **32%** of France's, Dublin's metro dominates Ireland — but New York
is only **~8%** of US GDP and Washington ~3%. So "punch out" each country's capital
and/or largest metro and re-rank on the **hinterland**: does the median bit of America
still out-earn the median bit of Europe once the global cities are removed? This is the
crux of the US-vs-Europe productivity debate (Krugman et al.).

Empirically (per-capita PPP, both metros removed): the US loses **~3%** and *rises* to
#3; France loses **~16%**, Ireland **~40%**. Removing Berlin actually *raises* Germany's
average (Berlin is below the national mean) — a real, instructive effect.

## Phase 1 — country-level (shipped)
- **Data:** OECD **Functional Urban Areas — "Economy"** (`DSD_FUA_ECO@DF_ECONOMY`):
  one consistent FUA methodology across the US, Europe, Japan, Korea, etc. Each metro
  carries **GDP as % of national value** (the carve-out), PPP GDP, and derived
  population (GDP ÷ GDP-per-person). National totals from World Bank WDI. 30 countries,
  ~550 metros. Compiled to `data/processed/subnational_metros.parquet`
  (`app/services/subnational_gdp/metros.py`).
- **Removal rules** (`model.select_removed_metros`): *largest* = top-GDP FUA; *capital*
  = the capital's FUA (code map, e.g. Washington `USA04F`, Wellington `NZL03F`, else
  `<prefix>001F`/`<prefix>01F`); *both* and they coincide (London, Paris, Tokyo) ⇒ also
  drop the next-largest, so two distinct metros come out.
- **Carve-out:** `rest_gdp = national × (1 − Σ metro GDP shares)`,
  `rest_pop = national_pop − Σ metro_pop`, recomputed on all three bases. The US enters
  as a single entity; non-OECD countries and US states are hidden in this view.
- **Widget:** "Punch out global cities" toggles (Capital / Largest). Hinterland ladder
  animates the reshuffle; each row shows the removed metros. `/api/subnational-gdp/hinterland`
  mirrors it; tests pin the US-robust / Europe-fragile result and the fallback rule.

## Phase 2 — per-US-state punch-out (BUILT)
Each **state** also strips its own metro (Colorado − Denver; New York − the NY part of the
NYC metro), so states and hinterland-countries sit on one ladder.

**What shipped** (`app/services/subnational_gdp/us_metros.py`, dataset `us_state_metros`):
- **Footprint = Combined Statistical Area (CSA)**, CBSA fallback — the broad
  commuting-zone definition, comparable to OECD's FUAs. The NY CSA pulls in the Hudson
  Valley (Poughkeepsie/Newburgh), Bridgeport, etc., so NY State is stripped of a
  comparably-big metro (NY-state slice $1.86T, 13.8M).
- **Split across states by county:** BEA county GDP `CAGDP2` (place of work) and county
  population `CAINC1` (residence) + Census/OMB 2023 CSA delineation. State totals are
  county sums (so a metro's GDP share is exact and the hinterland is precisely the
  non-metro counties). Cross-border commuters net out by construction.
- States are modelled as `place` dicts identical in shape to countries, so the same
  `select_removed_metros` / `hinterland_table` handle both; the ladder shows states +
  countries + USA-whole, with the kind filter (states / countries / all).
- **No-hinterland guard:** places left with < 12% of their population *or* GDP (New
  Jersey, Rhode Island, Massachusetts, Connecticut, Maryland… — essentially all metro)
  are dropped rather than shown as an unstable ratio. 43 of 51 states survive.
- Capital-vs-largest per state mirrors the national rule (NY: Albany≠NYC → both removes
  two; Colorado: Denver is capital *and* largest → fall back to Colorado Springs). Tests
  pin the CSA footprint, the capital/largest split, and the combined ladder.

**Known limitation / choice:** US states use the **CSA** footprint while countries use the
**OECD FUA** — a deliberate, documented break. OECD doesn't expose US FUA→county membership
via its API (`DF_LAU` returns no US records), so CSA is the closest broad proxy. For the
record, a fully OECD-consistent US split would need:

1. **County GDP** from BEA `CAGDP2` (county GDP, current $; the `BEA_API_KEY` works) and
   **county population** from BEA `CAINC1` — both already in reach.
2. **County→metro crosswalk** from the Census/OMB CBSA delineation file (county FIPS →
   CBSA). Confirm a license-clean, reachable URL (census.gov) under the network policy.
3. For each state: its **largest metro's in-state portion** = Σ GDP of that metro's
   counties that lie in the state (and likewise population); its **capital metro** =
   the metro containing the state-capital county. Apply the same capital/largest/both
   toggles per state. This does the cross-border split *by actual county GDP*, which is
   better than the population-proportional brute force the maintainer suggested — though
   that remains a fallback where county GDP is missing.

**Open methodological choices for Phase 2:**
- US states would use a *US* metro definition (CBSA) while countries use OECD FUA — a
  deliberate, documented consistency break (the maintainer accepted "best effort" here).
- "Largest metro of a state" — by in-state GDP, or by the metro's total GDP even if its
  core is in a neighbour state? (e.g. is NJ's "largest" the NY metro's NJ slice?)
- Some European countries have the same cross-border issue (e.g. metros near borders);
  out of scope while the comparison is US-states-vs-whole-countries.

## Acceptance criteria
- **Phase 1 (met):** OECD FUA metros compiled; capital/largest/both with fallback;
  hinterland ladder on all bases; US-robust/Europe-fragile pinned by tests; non-OECD hidden.
- **Phase 2:** each US state shows its hinterland with cross-border metros split by county;
  states and countries co-ranked; sources/definitions surfaced.

## Notes / risks
- OECD FUA latest year is ~2021–2023; metro *shares* move slowly, so applying them to
  current World Bank national totals is acceptable (flagged in the UI).
- Metro population is OECD-derived; mixing it with World Bank national population is a
  minor inconsistency, surfaced as a caveat.
