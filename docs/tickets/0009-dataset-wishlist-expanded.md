# Ticket 0009 — Expanded Dataset Wishlist & Followup Plan

**Status:** open (maintainer action required — see followup items below)
**Owner:** maintainer provisions access; Claude wires catalog + services
**Created from:** user request to expand beyond ticket 0006 with housing, employment,
international trade, commodities, and more equity data sources.

---

## Summary

Expands the data access wishlist (ticket 0006) into a full prioritised source catalog
across seven categories. The machine-readable deliverable is `_wishlist_env.env` at
the repo root — scan it, fill in keys, and tell Claude which vars are set.

Key additions requested:
- **Housing market**: Zillow Research, Redfin Data Center (both free CSV), HUD (free key)
- **Employment**: ADP National Employment Report (free CSV), BLS JOLTS
- **International trade**: UN Comtrade Plus, CEPII BACI, WTO Stats
- **Energy & commodities**: EIA Open Data (free key), World Bank Pink Sheet (free)
- **Equities**: Polygon.io, Finnhub, Tiingo (all freemium with generous free tiers)
- **Alternative**: Google Trends / Pytrends, Our World in Data, Opportunity Insights

---

## A. Priority provisioning (free keys, high impact)

| Env var | Provider | Signup | Impact |
|---|---|---|---|
| `FRED_API_KEY` | St. Louis Fed | https://fred.stlouisfed.org/docs/api/api_key.html | ⚠️ **empty now** — unlocks 800k macro series |
| `CENSUS_API_KEY` | US Census | https://api.census.gov/data/key_signup.html | ⚠️ **empty now** — blocks median-income service (ticket 0007) |
| `EIA_API_KEY` | US EIA | https://www.eia.gov/opendata/register.php | New — all US energy/commodity data, free |
| `UN_COMTRADE_API_KEY` | UN | https://comtradeplus.un.org/ | New — best global trade-flow data |
| `FINNHUB_API_KEY` | Finnhub | https://finnhub.io/register | New — 60/min free; fundamentals + macro |
| `TIINGO_API_KEY` | Tiingo | https://www.tiingo.com/ | New — full history EOD total returns |
| `POLYGON_API_KEY` | Polygon.io | https://polygon.io/ | New — US market breadth, delayed free tier |
| `HUD_API_KEY` | HUD USER | https://www.huduser.gov/hudapi/public/register | New — official rent benchmarks (FMR) |

**No-key sources that are ready to acquire immediately** (just need egress allowlist):
- Zillow Research CSVs (`zillow.com`)
- Redfin Data Center CSVs (`redfin.com`)
- World Bank Pink Sheet (`thedocs.worldbank.org`)
- Our World in Data GitHub (`raw.githubusercontent.com/owid/`)
- Opportunity Insights (`opportunityinsights.org`)
- ECB SDW (`data-api.ecb.europa.eu`)
- Bank of England (`www.bankofengland.co.uk`)
- BIS bulk downloads (`www.bis.org`)
- CEPII BACI (`www.cepii.fr` — requires free registration)
- WTO Stats (`apiportal.wto.org`)
- UNCTAD Stats (`unctadstat.unctad.org`)
- ADB Key Indicators (`kidb.adb.org`)

---

## B. Paid sources worth considering

| Source | Cost | Why | Substitute |
|---|---|---|---|
| **TradingEconomics** | ~$50/mo+ | 300k indicators, 196 countries, exceptional breadth for international macro | World Bank + IMF + Eurostat cover most things; TE for the gaps |
| **Numbeo API** | ~$50/mo | City cost-of-living detail (rents, groceries, healthcare) | BEA RPP + OECD price levels + national stats for most cases |
| **Polygon paid tier** | $29/mo | 15-min delayed US data + options | Free tier covers most historical analysis |
| **Glassnode Standard** | $39/mo | On-chain crypto analytics | CoinGecko free for basic crypto |

---

## C. The unstructured-international-data problem

The user noted that many countries (e.g. Ethiopia ESS) publish trade statistics as
PDFs or inconsistently-formatted Excel files. This is not a key problem — it's a
parsing and acquisition skill problem.

**Recommended approach** (followup skill to build):

1. **`ingest-document` skill** — a PDF/Excel→parquet skill that:
   - Accepts a URL to a report (PDF or Excel)
   - Uses Claude's vision/document capabilities to extract tables
   - Normalizes column names, units, and time periods
   - Writes to `data/raw/<id>/` and a tidy parquet

2. **National stats office registry** — a YAML mapping:
   ```yaml
   # docs/national_stats_offices.yaml
   ethiopia:
     name: "Ethiopian Statistics Service"
     homepage: "https://ess.gov.et"
     trade_report_pattern: "https://ess.gov.et/wp-content/uploads/{year}/{month}/external-merchandise-trade-statistics-*.pdf"
     format: pdf
   nigeria:
     name: "National Bureau of Statistics"
     homepage: "https://www.nigerianstat.gov.ng"
     # ...
   ```

3. **Covered priority countries** (from major non-OECD economies already in the
   `nonoecd_metros` dataset): China, India, Brazil, Russia, Indonesia, Saudi Arabia,
   Argentina, South Africa, Egypt, Nigeria, Thailand, Philippines, Vietnam.

4. **Existing structured paths**: Before building the PDF skill, check if the country
   has data on UN Comtrade, World Bank, or IMF — most African/Asian trade data *is*
   there, just slower/less granular than the national source.

---

## D. Catalog entries to add (once access lands)

New catalog IDs to wire (in addition to existing placeholders in ticket 0006):

### Housing
- `zillow_zhvi` — Zillow Home Value Index (CSV, key-free)
- `zillow_zori` — Zillow Observed Rent Index (CSV, key-free)
- `redfin_market` — Redfin weekly/monthly market data (CSV, key-free)
- `hud_fmr` — HUD Fair Market Rents by metro (`HUD_API_KEY`)

### Employment
- `adp_employment` — ADP payroll employment by sector (CSV, key-free)
- `bls_jolts` — JOLTS: job openings, hires, separations (`BLS_API_KEY`)
- `bls_qcew` — Quarterly Census of Employment and Wages (`BLS_API_KEY`)

### Trade
- `un_comtrade` — bilateral trade flows (`UN_COMTRADE_API_KEY`)
- `cepii_baci` — harmonized bilateral trade at HS6 (free bulk download)
- `wto_tariff` — tariff rates by country/product (`WTO_API_KEY`)
- `imf_dots` — IMF Direction of Trade Statistics (key-free)
- `unctad_stats` — UNCTAD development indicators (key-free)

### Energy & Commodities
- `eia_energy` — US + global energy data (`EIA_API_KEY`)
- `wb_pink_sheet` — World Bank commodity prices (key-free)
- `opec_momr` — OPEC monthly market data (PDF/Excel, key-free)

### Equities & Finance
- `polygon_stocks` — US equities (`POLYGON_API_KEY`)
- `finnhub` — global stocks + macro (`FINNHUB_API_KEY`)
- `tiingo_eod` — US/global EOD total returns (`TIINGO_API_KEY`)
- `ecb_sdw` — ECB monetary/financial stats (key-free)
- `boe_stats` — Bank of England stats (key-free)
- `bis_stats` — BIS banking/FX/property stats (key-free)

### Alternative
- `owid` — Our World in Data (key-free, GitHub CSVs)
- `opportunity_insights` — Harvard mobility data (key-free)
- `coingecko` — crypto market data (`COINGECKO_API_KEY` optional)

---

## E. Acceptance criteria

- `_wishlist_env.env` at repo root documents all sources with signup URLs.
- Maintainer provisions keys from section A and sets them in the environment.
- For each key set: Claude adds catalog entry + wires acquire/compile.
- No-key sources: egress allowlist extended for domains in section A.
- For the unstructured-data problem: followup ticket created when maintainer
  wants to tackle a specific country's data.

---

## Notes

- The `_wishlist_env.env` file is the authoritative source for env var names.
  When the maintainer provisions a key, they set the exact var name from that file.
- Redfin and Zillow data are free for research but not for redistribution — do not
  commit raw files to the repo; acquire at build time only.
- ADP, Indeed, and Challenger data have no machine-readable API; they require
  scheduled downloads or scraping. Wire after the core API sources are done.
- For equities: Tiingo has the best free tier for long-run backtesting;
  Finnhub for fundamentals; Polygon for breadth. All three together cover 95%
  of equity research needs for free.
