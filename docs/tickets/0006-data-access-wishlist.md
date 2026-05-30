# Ticket 0006 — Data access wishlist & rate-limit tracking

**Status:** open (infra/enablement — tracks external access the maintainer is provisioning)
**Owner:** maintainer provisions access; Claude wires catalog entries + usage tracking

## Summary
Records the external data access being opened up for the acquire/compile skills,
and the policy for sources that are free only up to a request limit: **treat them
as free, but track usage so we stay under the limit.** Paid sources are captured
as a wishlist, not yet provisioned.

This ticket exists because the environment's network policy initially blocked all
non-GitHub egress, forcing datasets through GitHub-hosted mirrors (JST via
`forex-centuries`, Shiller via `datasets/s-and-p-500`). The items below let the
skills pull from canonical primary sources instead.

---

## A. Free unblocks (being provisioned now)

### Network egress allowlist — key-free official APIs
Adding these hosts unblocks most of the catalogue with no credentials:
- `api.worldbank.org` — World Bank indicators (`worldbank_indicators`)
- `www.imf.org` — IMF DataMapper (`imf_datamapper`)
- `ec.europa.eu` — Eurostat (`eurostat`)
- `sdmx.oecd.org` — OECD SDMX (`oecd`)
- `www.federalreserve.gov` — SCF + DFA wealth/income (`fed_scf`, `fed_dfa`)
- `pages.stern.nyu.edu` — Damodaran historical returns (`damodaran_histret`)
- `api.stlouisfed.org` / `fred.stlouisfed.org` — FRED (`fred`)
- `apps.bea.gov` — BEA Regional (`bea_regional`)
- `www.macrohistory.net` — JST from source (replace the mirror in `jst_returns`)
- `api.census.gov`, `api.bls.gov` — for the new entries in section C

### Free API keys (env vars — names are read verbatim by `DatasetSpec.resolved_api_key`)
| Env var | Provider | Signup | Catalog id |
|---|---|---|---|
| `FRED_API_KEY` | St. Louis Fed | free, instant | `fred` |
| `BEA_API_KEY` | US BEA | free, instant | `bea_regional` |
| `CENSUS_API_KEY` | US Census | free, instant | (new, section C) |
| `BLS_API_KEY` | US BLS | free, instant | (new, section C) |

> When a key is set, tell Claude the exact env-var name used and the catalog
> `api_key:` field will be wired to match.

### Observed key status (as of the subnational-GDP build, ticket 0002)
The keyed env vars are all *present*, but several are **empty strings** — the var
exists with no value, so `os.environ.get(...)` returns `""` and auth fails. Verified
by actually hitting each API:

| Env var | Status | Verified against |
|---|---|---|
| `BEA_API_KEY` | ✅ working (36-char key) | BEA Regional SAGDP2 / SASUMMARY |
| `BLS_API_KEY` | ✅ working (32-char key) | BLS v2 CPI series |
| `ALPHAVANTAGE_API_KEY` | set (16-char, untested) | — |
| `FRED_API_KEY` | ⚠️ **empty** | FRED rejects (needs 32-char key) |
| `CENSUS_API_KEY` | ⚠️ **empty** | Census returns "Missing Key" |
| `NASDAQ_DATA_LINK_API_KEY` | ⚠️ **empty** | — |

Key-free official sources confirmed reachable from canonical URLs (no mirror needed):
**World Bank** (`api.worldbank.org`) and **IMF DataMapper** (`www.imf.org`) — both
fetched live for ticket 0002. To unblock the next services, the empty keys
(`CENSUS_API_KEY` for ticket 0007 median income; `FRED_API_KEY` as a general backup)
need real values provisioned.

---

## B. Free-but-rate-limited — usage tracking policy
These cost nothing but cap requests. **Policy: use freely, but log every call and
stay comfortably under the limit.** Limits below are approximate — verify against
current provider docs before relying on them.

| Source | Free tier limit (approx) | Notes |
|---|---|---|
| FRED | ~120 requests/min, no daily cap | batch series; cache raw responses |
| BEA | ~100 requests/min, 100 MB/min | cache; one pull covers many years |
| Census | ~500 queries/day per key | prefer wide queries over many narrow ones |
| BLS v2 (registered) | 500 queries/day, 50 series/query | v1 unregistered is only 25/day |
| World Bank / IMF / Eurostat / OECD | no key; fair-use only | avoid tight loops; cache aggressively |
| Nasdaq Data Link (Quandl) | ~50 calls/day anon; higher with free key | section C |
| Alpha Vantage | 25 requests/day, 5/min | section C; very tight — cache hard |

### Tracking mechanism (to implement)
- Add optional catalog fields per dataset: `free_tier_limit` (e.g. `"500/day"`)
  and `rate_note`.
- Have the HTTP source layer (`backend/app/core/sources/http.py`) append a line to
  a local ledger (`data/.usage_log.jsonl`: timestamp, dataset id, url) on each
  fetch of a limited source, and warn when the trailing-window count approaches
  the declared limit.
- Keep raw pulls cached in `data/raw/<id>/` (already the pattern) so re-compiles
  never re-hit the API.
- The acquire-dataset skill should consult the ledger before bulk pulls.

---

## C. Catalog entries to add once access lands (free / freemium)
Stage as `acquire/compile not yet wired`, mirroring existing placeholder entries:
- **BLS** (`bls`, `BLS_API_KEY`) — CPI detail, employment, wages.
- **US Census** (`census`, `CENSUS_API_KEY`) — ACS demographics, income, housing.
- **Nasdaq Data Link / Quandl** (`nasdaq_data_link`, `NASDAQ_DATA_LINK_API_KEY`) —
  broad financial/commodity series; rate-limited free tier.
- **Alpha Vantage** (`alpha_vantage`, `ALPHAVANTAGE_API_KEY`) — equities/FX; only
  if a use case needs it (25/day is very tight).

---

## D. Paid wishlist (not provisioned — capture only)
Each maps to a concrete planned service; provision only if the free substitutes
prove insufficient.

| Source | Cost shape | Why / which ticket | Substitute first? |
|---|---|---|---|
| **Numbeo API** (`NUMBEO_API_KEY`) | paid per-request / subscription | richest city-level rent/grocery/healthcare for the flagship cost-of-living service (0005) | yes — OECD/Eurostat price levels + BEA RPP + national stats offices |
| **JSTOR / academic** | institutional | sourcing & citing historical datasets (e.g. pre-1945 currency circulation, ticket 0001) and methodology grounding for deep-research; **literature, not a data pipeline** | yes — FRED/NBER/national archives for the actual series |
| **Statista / CEIC / Refinitiv** | enterprise | only if a question truly needs proprietary coverage | almost always yes |

---

## Acceptance criteria
- Allowlisted key-free sources fetch successfully from canonical URLs (not mirrors).
- Keyed sources resolve their env var and fetch; missing-key path fails clearly.
- Limited-tier sources have `free_tier_limit` recorded and a working usage ledger
  with a near-limit warning.
- Paid sources remain documented-only until explicitly provisioned; any use is
  cited and license/ToS-flagged in output (see 0005).

## Notes
- Env-var names are contractual: `DatasetSpec.resolved_api_key()` does
  `os.environ.get(self.api_key)`, so the catalog `api_key:` field must equal the
  exact variable name set in the environment.
- Prefer official, license-clean sources over aggregators wherever both exist.
