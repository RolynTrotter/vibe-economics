---
name: acquire-dataset
description: >
  Find and download the raw data needed to answer an economics question in
  vibe-economics. Use when a question needs a dataset the repo doesn't have yet
  (GDP, returns, prices, wealth, currency, cost of living, etc.). Identifies an
  authoritative, preferably key-free and license-clean source, registers it in
  data/catalog.yaml, and downloads raw files into data/raw/<id>/.
---

# acquire-dataset

Stage 1 of the four-stage flow (acquire → compile → analyze → build-widget).
Your job: turn "I need data about X" into a registered, downloaded raw dataset.

## Steps

1. **Check what we already have.** Read `data/catalog.yaml` and `docs/datasets.md`.
   If a suitable dataset is already registered, skip to compile.

2. **Pick a source.** Prefer, in order:
   - free + key-less + license-clean (World Bank, IMF DataMapper, Eurostat, OECD,
     Shiller, Fed DFA/SCF, BEA, Census, BLS);
   - free-with-key (FRED, BEA) — read the key from the documented env var, never
     commit it;
   - proprietary / ToS-restricted (e.g. Numbeo ⚠️) — only as a last resort, only
     with a valid key, and only within the source's terms. Flag the limitation in
     the catalog and prefer an official substitute when one exists.
   When unsure which source is authoritative, do a quick web search and note the
   homepage. Verify the download URL actually returns data before committing to it.

3. **Register it** in `data/catalog.yaml` with a stable snake_case `id` and all
   fields (title, source, homepage, url, license, api_key, raw, processed,
   compiler, notes). Add a row to `docs/datasets.md` too.

4. **Download** into `data/raw/<id>/` using the generic fetcher in
   `backend/app/core/sources/` (or `python -m app.cli acquire <id>` once wired).
   Raw files are gitignored — the catalog records how to refetch them.

5. **Verify** the file is the expected type/size and is parseable (open it, peek
   at the first rows/sheets). Report what you got.

## Conventions
- Network access requires the sandbox to be off for the download command.
- Don't hardcode secrets. Keys come from env vars named in the catalog.
- Note units, coverage (years, geographies), and any redistribution limits.

## Worked example
`shiller_returns` (Shiller `ie_data.xls`) is the reference acquisition: key-free,
license-clean, registered in `data/catalog.yaml`, fetched into
`data/raw/shiller_returns/`. Mirror its catalog entry shape.

## Next stage
Hand off to **compile-dataset** to turn the raw download into tidy parquet.
