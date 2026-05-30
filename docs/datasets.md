# Data sources catalog

Human-readable companion to [`data/catalog.yaml`](../data/catalog.yaml) (the
machine-readable registry). When you need data for a new question, check here
first; the `acquire-dataset` skill consults this list.

Prefer sources that are **free, key-less, and license-clean**. Sources needing a
key read it from an env var (never commit keys). Proprietary/ToS-restricted
sources are flagged ⚠️.

## Returns / markets (for backtesting)

| Source | What | Key? | License | Notes |
|--------|------|------|---------|-------|
| **Shiller (Yale)** | S&P 500 price/div/earnings, CPI, 10yr rate, monthly since 1871 | no | personal/academic, cite | Primary for safe-withdrawal. `ie_data.xls`. |
| **Damodaran (NYU)** | Annual stocks/T.bonds/T.bills/inflation since 1928 | no | educational | Backup returns series. |
| FRED | Almost any macro/market series | yes (free) | varies | General backup. |

## National & subnational economic accounts

| Source | What | Key? | License | Notes |
|--------|------|------|---------|-------|
| **World Bank WDI** | GDP, GDP PPP, population, income, by country & year | no | CC BY 4.0 | Key-free REST/JSON. |
| **IMF DataMapper** | WEO indicators (GDP USD/PPP) | no | attribution | Key-free. |
| **BEA Regional** | US state/county GDP, personal income | yes (free) | public domain | For US states vs Europe. |
| **Eurostat** | EU regional GDP, GDP/capita PPS, income | no | free reuse + attribution | JSON-stat API. |
| **OECD** | Comparative price levels, PPPs, regional wellbeing | no | attribution | SDMX JSON. |

## Wealth & income distribution

| Source | What | Key? | License | Notes |
|--------|------|------|---------|-------|
| **Fed SCF** | Survey of Consumer Finances: wealth/income by group | no | public domain | Triennial, deep detail. |
| **Fed DFA** | Distributional Financial Accounts: wealth by percentile, quarterly | no | public domain | CSV, time series. |
| Census / BLS | Income, CPI, regional prices | no/mixed | public domain | National statistics. |

## Cost of living (city level)

| Source | What | Key? | License | Notes |
|--------|------|------|---------|-------|
| ⚠️ **Numbeo** | City rent/groceries/healthcare indices | yes (paid) | proprietary | Richest but license-gray. Use only with key + within ToS. |
| **OECD price levels** | Comparative price levels by country | no | attribution | License-clean partial substitute. |
| **Eurostat HICP / price levels** | EU price levels & inflation | no | free reuse | For EU side of comparisons. |
| **BLS / national stat offices** | Official CPI & regional price parities | no | public domain | e.g. BEA Regional Price Parities for US metros. |
| **BEA RPP** | US regional price parities by metro/state | yes (free) | public domain | License-clean US city cost differences. |

## Currency circulation

| Source | What | Key? | License | Notes |
|--------|------|------|---------|-------|
| **BIS** | FX turnover (Triennial Survey), reserves | no | attribution | Modern "most traded". |
| **IMF COFER** | Currency composition of FX reserves | no | attribution | Reserve-currency share. |
| **SWIFT RMB Tracker** | Payment currency shares | mixed | proprietary-ish | Payments metric. |
| Historical (books/series) | Pre-1945 sterling vs dollar | n/a | varies | The £→$ crossover needs historical reserve/trade data; see ticket 0001. |

---

### Adding a new source
1. Add a row here and a full entry in `data/catalog.yaml`.
2. Implement (or reuse) a fetcher in `backend/app/core/sources/` and a compiler.
3. Wire `acquire`/`compile` so `python -m app.cli acquire <id>` works.
