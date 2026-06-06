# Ticket 0010 — Negative productivity & value destruction

**Status:** planned (research/scoping — concept + data sourcing first)
**Service id:** `negative_productivity`

## Summary
Higher- vs lower-productivity jobs, firms, and sectors is uncontroversial. This
ticket asks the next question: **can an economic activity have *negative*
productivity** — destroy more value than it creates — and if so, **how do we
track it** from public, license-clean data?

"Negative productivity" is not one thing. Output is rarely literally negative, so
the phrase resolves into a handful of distinct, individually-measurable ideas.
The maintainer's intuition — *"high indebtedness, simply unable to turn a
profit"* — is the **firm-level value-destruction / zombie-firm** lens, which is
also the most cleanly trackable. We anchor there and add the macro lenses around it.

## What "negative productivity" can mean (and how each is measured)

| Lens | Definition | The marker | Trackable from |
|---|---|---|---|
| **1. Value subtraction** | Value-added (output value − cost of intermediate inputs) is **negative**: the activity is worth less than the inputs it consumes | VA < 0 at market/world prices | BEA GDP-by-industry value-added; classic in transition-economics ("value subtraction" at world prices, Senik-Leygonie & Hughes 1992) |
| **2. Negative marginal product of labour** | Adding a worker *reduces* total output (overstaffing, congestion, disorganisation; "Brooks's Law"; Lewis surplus labour) | ΔOutput/ΔLabour < 0 | Hard at macro scale; proxy via falling VA-per-hour while hours rise |
| **3. Negative productivity *growth*** | Real output per hour (labour productivity) or TFP **falls** over a window — a whole sector going backwards (construction, parts of healthcare; Baumol cost disease) | Δ(real VA / hour) < 0; ΔTFP < 0 | BLS Labor Productivity & Costs + Total Factor/Multifactor Productivity (KLEMS); Penn World Table TFP |
| **4. Economic-profit destruction (EVA)** | Return on invested capital **below** the cost of capital — destroys value even when *accounting* profit is positive | ROIC < WACC, persistently | SEC EDGAR financials; ROIC computable, WACC proxied per-sector |
| **5. Zombie firm** ⭐ | Old firm whose operating earnings don't even cover its **interest** — alive only by rolling over debt | Interest-coverage ratio (EBIT ÷ interest) **< 1 for ≥3 consecutive years**, firm age ≥10y | SEC EDGAR (firm level); BIS/OECD methodology |

⭐ = the maintainer's intuition, and the recommended core of the service.

### Attributes of a negative-productivity firm / sector
- **Can't cover interest from earnings** — interest-coverage ratio < 1 (the zombie marker).
- **Earns less than its capital costs** — ROIC < WACC (negative economic profit / EVA).
- **Survives on credit, not cash flow** — debt grows while EBIT/free cash flow stagnates or falls; persistent negative FCF funded by new borrowing or subsidy.
- **Output per worker is falling**, sometimes while headcount/capital rise (lenses 2–3).
- **Negative value-added** at undistorted prices (lens 1) — the strongest form.
- At the macro level: **sustained negative TFP growth** (lens 3) — the economy works harder for less.

> Why it matters: zombies and value-subtracting activity don't just under-perform —
> they **crowd out** healthier firms for capital and labour, dragging *aggregate*
> productivity down (Caballero–Hoshi–Kashyap on 1990s Japan; BIS Quarterly Review,
> Banerjee & Hofmann 2018/2020, which find the zombie share of listed firms rising
> across advanced economies).

## Questions it answers
- What share of listed firms are **zombies** (ICR < 1 for ≥3y), by sector and year? Is it rising?
- Which **industries went backwards** — negative real value-added-per-hour or negative TFP growth over the last 10–20 years?
- Which firms **destroy economic value** (ROIC < WACC) despite positive accounting profit?
- Which **country-years** had negative TFP growth (working harder for less)?

## Ways to track it (concrete measures to compute)
1. **Zombie share** — % of firms, and % of assets/employment, with EBIT/interest < 1 for ≥3 consecutive years (age ≥10y), by sector × year. *(BIS definition; from EDGAR.)*
2. **Value-subtraction ranking** — industries by *change* in real value-added per hour; surface the most-negative. *(BLS + BEA.)*
3. **Negative-TFP episodes** — country-years with TFP growth < 0. *(Penn World Table.)*
4. **EVA screen** — firms/sectors with ROIC < a sector cost-of-capital proxy. *(EDGAR.)*
5. **Debt-funded survival** — entities whose debt rises while EBIT/FCF is flat-to-falling (rollover dependence). *(EDGAR / Fed Z.1.)*

## Data sources (all key-free / public-domain candidates — see docs/datasets.md)
- **SEC EDGAR — Financial Statement Data Sets** (firm financials, bulk, public domain) → ICR, ROIC, leverage, FCF for lenses 4–5 and zombie share.
- **BLS Productivity** — Labor Productivity & Costs + Total Factor / Multifactor (KLEMS) productivity, by industry → lens 3.
- **BEA GDP-by-industry** — value-added by industry → lenses 1 & 3 (VA per worker).
- **Penn World Table** — cross-country TFP levels & growth (GitHub-mirrorable) → lens 3 macro.
- **OECD Productivity** (key-free SDMX) and **BIS** zombie research → cross-country benchmarking / methodology grounding.
- World Bank WDI (already in catalog) — crude GDP-per-worker fallback.

## Backend (sketch — mirrors the reference service shape)
- `data.py` — acquire+compile EDGAR financials and BLS/BEA industry productivity into tidy frames (`entity, sector, year, measure, value`).
- `model.py` (pure) — zombie flag, ICR, ROIC−WACC spread, VA-per-hour growth, TFP growth; aggregate to sector/year shares.
- Endpoints: `GET /api/negative-productivity/zombie-share?by=sector`,
  `/value-subtraction?metric=va_per_hour`, `/tfp?scope=country`.

## Frontend (sketch)
- Zombie-share time series (stacked by sector); "is it rising?" call-out.
- Ranked "industries going backwards" bar chart (most-negative productivity growth).
- Firm/sector EVA scatter (ROIC vs cost of capital; below-diagonal = value-destroying).

## Acceptance criteria
- A defensible, sourced **definition set** (this ticket) — done on merge.
- ≥1 trackable measure computed from real data (start with **zombie share from EDGAR**, the closest match to the maintainer's intuition).
- Macro cross-check: ≥1 negative-TFP or negative-VA-growth ranking from BLS/BEA/PWT.

## Notes / risks
- **Accounting ≠ economic loss:** a firm can post profits yet destroy value (ROIC < WACC), and a young loss-making firm investing for growth is *not* a zombie — the ≥3-year / age ≥10y screen exists precisely to exclude it. Keep the distinction explicit in the UI.
- **Price distortions:** lens 1 (value subtraction) only bites at *undistorted* prices; flag when inputs/outputs are subsidised or administered.
- **Survivorship & coverage:** EDGAR is US listed firms only; private and foreign firms are missing — state the universe plainly. Zombie shares are sensitive to the rate environment (cheap debt inflates them).
- **WACC is a proxy:** sector-level cost-of-capital approximations, not firm-exact; treat the EVA screen as a screen, not a verdict.
