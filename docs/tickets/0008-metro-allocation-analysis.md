# Ticket 0008 — Phase 2 analysis: how to split a metro across a state line

_Exploratory analysis (not app code). Generated from BEA county GDP (CAGDP2, all-industry, 2024, **place of work**), BEA county population (CAINC1, 2024, **residence**), and the Census/OMB 2023 CBSA delineation. OECD FUA figures from `subnational_metros`._

## The problem in one sentence

**GDP is counted where the work happens; population where people sleep.** A commuter living in New Jersey and working in Manhattan adds to *New York's* GDP but *New Jersey's* population. So when a metro straddles a state line, the way you split it flips each side's per-capita. The three candidate methods:

| Method | What it allocates by | Captures commuting? |
|---|---|---|
| **By county GDP** (place of work) | each state's metro-county GDP, as BEA measures it | **Yes** — commuter output stays in the work-state, where it's actually booked |
| **By county population** (residence) | metro GDP split by where metro residents live | No — hands the work-state's output to the bedroom states |
| **By population (OECD FUA)** | OECD's single whole-metro figure, split by residents | No — and OECD's US footprint is *“Greater”* (CSA-like; e.g. Greater Washington includes Baltimore), so it doesn't even match the CBSA |

The gap between the first two is the **commuter Δ** (place-of-work GDP minus population-allocated GDP): positive = a net *importer* of commuters (produces more than its residents would); negative = a *bedroom* exporter.

## Summary — the six you named (+ four notable tri-state metros)

| Metro | States | Metro GDP | Net commuter **importer** (Δ) | Net **exporter** (Δ) |
|---|---|--:|--:|--:|
| New York-Newark-Jersey City | NY–NJ | $2442.5B | **NY +$222.0B** | NJ $-222.0B |
| Washington-Arlington-Alexandria | MD–DC–VA–WV | $529.6B | **DC +$101.6B** | MD $-85.7B |
| Chicago-Naperville-Elgin | IL–IN | $923.1B | **IL +$27.7B** | IN $-27.7B |
| Philadelphia-Camden-Wilmington | PA–NJ–DE–MD | $582.1B | **DE +$21.9B** | NJ $-25.6B |
| St. Louis | MO–IL | $236.8B | **MO +$17.8B** | IL $-17.8B |
| Kansas City | MO–KS | $188.2B | **KS +$10.8B** | MO $-10.8B |
| Cincinnati | OH–KY–IN | $207.3B | **OH +$10.0B** | KY $-6.3B |
| Portland-Vancouver-Hillsboro | OR–WA | $225.3B | **OR +$14.1B** | WA $-14.1B |
| Memphis | TN–MS–AR | $107.5B | **TN +$10.6B** | MS $-9.2B |
| Charlotte-Concord-Gastonia | NC–SC | $277.1B | **NC +$16.6B** | SC $-16.6B |

## Per-metro detail

### New York-Newark-Jersey City, NY-NJ
Metro (CBSA, place of work): **$2442.5B GDP, 19.9M residents**.

| State | Cty | By county **GDP** (PoW) | Residents | By **population** →GDP | GDP/capita (PoW) | Commuter Δ |
|---|--:|--:|--:|--:|--:|--:|
| **NY** | 10 | $1797.2B | 12.86M (64%) | $1575.2B | $140k | +$222.0B |
| **NJ** | 12 | $645.3B | 7.08M (36%) | $867.3B | $91k | $-222.0B |

_OECD FUA “New York (Greater)”: $1862.3B GDP, 20.2M (PPP). Footprint ≈ CBSA._

### Washington-Arlington-Alexandria, DC-VA-MD-WV
Metro (CBSA, place of work): **$529.6B GDP, 4.5M residents**.

| State | Cty | By county **GDP** (PoW) | Residents | By **population** →GDP | GDP/capita (PoW) | Commuter Δ |
|---|--:|--:|--:|--:|--:|--:|
| **MD** | 4 | $211.6B | 2.52M (56%) | $297.2B | $84k | $-85.7B |
| **DC** | 1 | $184.3B | 0.70M (16%) | $82.7B | $262k | +$101.6B |
| **VA** | 9 | $130.7B | 1.21M (27%) | $142.4B | $108k | $-11.7B |
| **WV** | 1 | $3.0B | 0.06M (1%) | $7.2B | $50k | $-4.2B |

_OECD FUA “Washington (Greater)”: $780.8B GDP, 9.3M (PPP). Footprint is wider than the CBSA (CSA-like) — not splittable to states._

### Chicago-Naperville-Elgin, IL-IN
Metro (CBSA, place of work): **$923.1B GDP, 9.4M residents**.

| State | Cty | By county **GDP** (PoW) | Residents | By **population** →GDP | GDP/capita (PoW) | Commuter Δ |
|---|--:|--:|--:|--:|--:|--:|
| **IL** | 9 | $879.5B | 8.68M (92%) | $851.9B | $101k | +$27.7B |
| **IN** | 4 | $43.6B | 0.73M (8%) | $71.3B | $60k | $-27.7B |

_OECD FUA “Chicago”: $712.2B GDP, 9.4M (PPP). Footprint ≈ CBSA._

### Philadelphia-Camden-Wilmington, PA-NJ-DE-MD
Metro (CBSA, place of work): **$582.1B GDP, 6.3M residents**.

| State | Cty | By county **GDP** (PoW) | Residents | By **population** →GDP | GDP/capita (PoW) | Commuter Δ |
|---|--:|--:|--:|--:|--:|--:|
| **PA** | 5 | $397.0B | 4.25M (67%) | $390.7B | $93k | +$6.3B |
| **NJ** | 4 | $102.0B | 1.39M (22%) | $127.6B | $74k | $-25.6B |
| **DE** | 1 | $76.0B | 0.59M (9%) | $54.1B | $129k | +$21.9B |
| **MD** | 1 | $7.2B | 0.11M (2%) | $9.8B | $67k | $-2.6B |

_OECD FUA “Philadelphia (Greater)”: $486.0B GDP, 6.6M (PPP). Footprint ≈ CBSA._

### St. Louis, MO-IL
Metro (CBSA, place of work): **$236.8B GDP, 2.8M residents**.

| State | Cty | By county **GDP** (PoW) | Residents | By **population** →GDP | GDP/capita (PoW) | Commuter Δ |
|---|--:|--:|--:|--:|--:|--:|
| **MO** | 7 | $198.0B | 2.14M (76%) | $180.2B | $93k | +$17.8B |
| **IL** | 8 | $38.7B | 0.67M (24%) | $56.6B | $58k | $-17.8B |

_OECD FUA “St. Louis”: $172.2B GDP, 2.6M (PPP). Footprint ≈ CBSA._

### Kansas City, MO-KS
Metro (CBSA, place of work): **$188.2B GDP, 2.3M residents**.

| State | Cty | By county **GDP** (PoW) | Residents | By **population** →GDP | GDP/capita (PoW) | Commuter Δ |
|---|--:|--:|--:|--:|--:|--:|
| **MO** | 9 | $99.6B | 1.32M (59%) | $110.4B | $75k | $-10.8B |
| **KS** | 5 | $88.6B | 0.93M (41%) | $77.8B | $95k | +$10.8B |
### Cincinnati, OH-KY-IN
Metro (CBSA, place of work): **$207.3B GDP, 2.3M residents**.

| State | Cty | By county **GDP** (PoW) | Residents | By **population** →GDP | GDP/capita (PoW) | Commuter Δ |
|---|--:|--:|--:|--:|--:|--:|
| **OH** | 5 | $167.7B | 1.75M (76%) | $157.6B | $96k | +$10.0B |
| **KY** | 7 | $36.1B | 0.47M (20%) | $42.4B | $77k | $-6.3B |
| **IN** | 3 | $3.5B | 0.08M (3%) | $7.3B | $43k | $-3.7B |

_OECD FUA “Cincinnati”: $156.6B GDP, 2.2M (PPP). Footprint ≈ CBSA._

### Portland-Vancouver-Hillsboro, OR-WA
Metro (CBSA, place of work): **$225.3B GDP, 2.5M residents**.

| State | Cty | By county **GDP** (PoW) | Residents | By **population** →GDP | GDP/capita (PoW) | Commuter Δ |
|---|--:|--:|--:|--:|--:|--:|
| **OR** | 5 | $191.5B | 2.00M (79%) | $177.4B | $96k | +$14.1B |
| **WA** | 2 | $33.9B | 0.54M (21%) | $47.9B | $63k | $-14.1B |

_OECD FUA “Portland”: $170.3B GDP, 2.4M (PPP). Footprint ≈ CBSA._

### Memphis, TN-MS-AR
Metro (CBSA, place of work): **$107.5B GDP, 1.3M residents**.

| State | Cty | By county **GDP** (PoW) | Residents | By **population** →GDP | GDP/capita (PoW) | Commuter Δ |
|---|--:|--:|--:|--:|--:|--:|
| **TN** | 3 | $92.2B | 1.02M (76%) | $81.6B | $91k | +$10.6B |
| **MS** | 5 | $12.9B | 0.28M (21%) | $22.1B | $47k | $-9.2B |
| **AR** | 1 | $2.3B | 0.05M (3%) | $3.7B | $50k | $-1.4B |

_OECD FUA “Memphis”: $81.1B GDP, 1.3M (PPP). Footprint ≈ CBSA._

### Charlotte-Concord-Gastonia, NC-SC
Metro (CBSA, place of work): **$277.1B GDP, 2.9M residents**.

| State | Cty | By county **GDP** (PoW) | Residents | By **population** →GDP | GDP/capita (PoW) | Commuter Δ |
|---|--:|--:|--:|--:|--:|--:|
| **NC** | 8 | $250.8B | 2.44M (84%) | $234.2B | $103k | +$16.6B |
| **SC** | 3 | $26.3B | 0.45M (16%) | $43.0B | $59k | $-16.6B |

_OECD FUA “Charlotte”: $177.7B GDP, 2.2M (PPP). Footprint is wider than the CBSA (CSA-like) — not splittable to states._

## What the tables show

- **The central jurisdiction always over-produces relative to its residents.** DC is the
  extreme: it books **$184B** of GDP but its **0.70M** residents would only "account for"
  **$83B** by population — a **+$102B** commuter import, and a place-of-work GDP/capita of
  **$262k** (vs ~$117k for the metro). Maryland (−$86B) and Virginia (−$12B) are the
  bedrooms that send those workers in.
- **New York–New Jersey is the same story at scale:** NY +$222B, NJ −$222B. Manhattan's
  output is partly produced by NJ and CT residents.
- Smaller metros are milder but consistent: the core state is always the importer
  (Chicago→IL +$28B, St. Louis→MO +$18B, Portland→OR +$14B, Charlotte→NC +$17B). Two flip
  the "expected" way: **Kansas City** (the **Kansas** side — Johnson County / Overland Park —
  is the net importer, +$11B) and **Philadelphia** (**Delaware**, +$22B — Wilmington's
  banking/chemical cluster pulls in PA/NJ/MD residents).

## Recommended method

**For the GDP cut, use county GDP (place of work). For the population cut, use county
population (residence). Remove the *same* metro counties from each state.**

Why this and not population-allocation:

1. **It preserves the accounting identity.** Summed county GDP *is* state GDP (that's how BEA
   builds it). Allocating a single metro GDP by residents breaks that — it would move DC's
   $100B of commuter output to Maryland and Virginia, which never booked it.
2. **It nets commuters out correctly.** A New Jersey→Manhattan commuter's *home* county leaves
   New Jersey's population and their *work* county leaves New York's GDP — together, in one
   move. The income they earn in New York was never in New Jersey's accounts to begin with, so
   nothing is double-counted or stranded.
3. **The OECD-population method fails twice for the US:** it's residence-based (wrong direction)
   *and* OECD's "Greater" FUAs are CSA-like — "Greater Washington" (9.3M) folds in Baltimore,
   so it doesn't even align with the Washington CBSA (4.5M). Don't split OECD figures to states.

Mapping to your three columns: **by county GDP** = the place-of-work column (use this for GDP);
**by county population** = the residents column / the population-allocated GDP (use county
population for the *population* cut only); **by population (OECD)** = the FUA note (don't use
for splitting).

### Definitions to make it concrete
- **A state's "largest metro"** = the metro with the largest *in-state* place-of-work GDP (so
  New Jersey's metro to remove is the **NJ slice of the NYC metro**, not all of NYC).
- **A state's "capital metro"** = the metro whose counties contain the state-capital county
  (Colorado→Denver, which is also largest; New York→Albany, distinct from NYC — same
  capital≠largest split we handle nationally).
- **Cross-border metros are cut on their in-state counties only.** Removing "NYC" from NY strips
  the NY counties; removing it from NJ strips the NJ counties. Each state keeps its own
  hinterland.

### One honest caveat
Heavy **bedroom states barely have a hinterland.** New Jersey is almost entirely inside the
NYC and Philadelphia metros, so "rest-of-NJ" is a sliver. That's a true feature, not an error —
but worth surfacing in the UI so a near-empty hinterland doesn't read as a data gap.

---

## Europe — where the same problem bites

**OECD FUAs are defined *within* national borders** — they don't cross them. So at the
country level (what our ladder compares), cross-border commuting doesn't split a metro; instead
it **inflates the work-country's GDP-per-capita**, because non-resident commuters produce GDP
that's divided by a residents-only denominator. This is the *national* version of the DC effect,
and it's exactly why some European per-capita numbers look high:

| Country | GDP/capita (PPP) | Why it's inflated | Right correction |
|---|--:|---|---|
| **Luxembourg** | ~$156k | **~47% of jobs are cross-border commuters** (frontaliers from FR/BE/DE; STATEC) | per-capita on *workers*, or remove cross-border GVA |
| **Ireland** | ~$133k | Multinational profit-shifting / IP onshoring (GDP ≫ GNI*) | use **GNI\*** (CSO Ireland) |
| **Switzerland** | ~$96k | **~390k cross-border workers** (~8% of jobs; ~25–30% in Geneva, ~27% in Ticino; Swiss FSO) | adjust Geneva/Ticino/Basel for frontaliers |
| **Norway** | ~$102k | Petroleum rents (not commuting) | mainland-GDP basis |

Removing a country's capital/largest metro **does not fix this** — the inflation is structural,
not concentrated in one removable city. These four should carry a "**per-capita inflated by
commuting / profit-shifting / resource rents**" flag in the hinterland view, the same spirit as
excluding DC.

### Cross-border *metros* (relevant if Phase 2 ever goes sub-national in Europe)
These are the European NYCs — single labour markets split by a national line. OECD splits them
into separate national FUAs, so the cross-border flow is invisible in each:

| Cross-border metro | Countries | Commuting flow (approx) |
|---|---|---|
| **Luxembourg** | LU ← FR, BE, DE | ~230k frontaliers into LU (largest in the EU) |
| **Geneva (Grand Genève)** | CH ← FR | ~110k French residents work in Geneva |
| **Basel (trinational)** | CH ← FR, DE | ~70k cross-border into Basel |
| **Øresund: Copenhagen–Malmö** | DK ↔ SE | ~15–20k SE→DK across the bridge |
| **Vienna–Bratislava** | AT ↔ SK | Slovak commuters into Lower Austria/Vienna; Bratislava's FUA (SK001F) hugs the border — *the case you flagged* |
| **Lille–Kortrijk–Tournai** | FR ↔ BE | Eurometropolis, ~tens of thousands both ways |
| **Aachen–Maastricht–Liège** | DE/NL/BE | Meuse-Rhine euregio |
| **Strasbourg–Kehl, Saarbrücken–Moselle** | FR ↔ DE | daily cross-Rhine commuting |

For **Slovakia specifically** (your example): Bratislava sits in the SK far-west corner on the
AT/HU tripoint, and a meaningful share of its labour market is oriented toward Vienna. If Phase 2
ever decomposes European countries into regions, Bratislava–Vienna would need the *same*
cross-border, place-of-work county/LAU allocation as NYC — but for the current **country-level**
comparison it's moot (we compare whole Slovakia to whole Austria), and the only action is the
commuter caveat on Luxembourg/Switzerland above.

## Bottom line
Adopt the **county-GDP (place of work) + county-population (residence)** method for US Phase 2;
it's the only consistent one and it captures commuting by construction. In Europe, the
equivalent problem shows up as **national per-capita inflation** (Luxembourg, Switzerland,
Ireland, Norway) rather than a splittable metro, so handle it with a **caveat/flag**, not a
punch-out.
