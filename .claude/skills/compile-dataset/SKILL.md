---
name: compile-dataset
description: >
  Transform a raw downloaded dataset into a tidy, analysis-ready parquet/csv in
  data/processed/ and finalize its data/catalog.yaml entry. Use after
  acquire-dataset has fetched raw files, or whenever a raw source needs cleaning
  into long, typed, unit-explicit form for a vibe-economics service.
---

# compile-dataset

Stage 2 of the four-stage flow. Your job: raw, messy source file → clean tidy
table the analysis code can trust.

## What "tidy" means here
- **Long format**: one observation per row (e.g. `year, series, value`), not wide
  spreadsheets with merged headers.
- **Typed**: numeric columns numeric, dates parsed, no stray text in number cols.
- **Explicit units**: a `unit` column or documented suffix; note nominal vs real
  and base year for any currency/return series.
- **Stable column names**: snake_case, documented in the catalog `notes`.
- **No surprises**: drop footnote rows, fix multi-row headers, handle the
  source's quirks (e.g. Shiller's date `1871.10` meaning Oct 1871).

## Steps
1. Read the raw file from `data/raw/<id>/` (path from `data/catalog.yaml`).
2. Write a compiler function `compile_<id>(raw_path) -> DataFrame` — put it near
   the service that owns the dataset (e.g.
   `app/services/<svc>/data.py:compile_<id>`) or in `app/core/` if shared.
3. Save to `data/processed/<id>.parquet` (parquet preferred; csv if you need it
   human-diffable and it's small).
4. Update `data/catalog.yaml`: set `processed` and `compiler`, refine `notes`
   (columns, units, coverage).
5. **Commit the processed file** — services run offline and results stay
   reproducible. (If it's large, gitignore it and document the rebuild command.)
6. Verify: load the parquet, check shape, dtypes, ranges, and a couple of known
   values. Report row count and coverage.

## Wire it into the CLI
`python -m app.cli compile <id>` should call your compiler. Add the dataset to
the dispatch in `app/cli.py` if needed.

## Worked example
`app/services/safe_withdrawal/data.py:compile_shiller` reads `ie_data.xls` and
emits `data/processed/shiller_returns.parquet` with columns
`year, stock_return, bond_return, inflation` (annual, real & nominal documented).

## Next stage
Hand off to **analyze-economics** to build the service that uses this table.
