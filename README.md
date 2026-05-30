# vibe-economics

A growing collection of small **economics utilities** — backtesting portfolios,
comparing subnational GDP, tracking currency circulation, exploring Fed
wealth/income data, comparing cost of living between places, and so on.

Each question becomes a **service**: a Python (FastAPI) endpoint that does the
data science, plus a mobile-first **React widget** so you can explore and verify
the findings on an Android phone in the browser.

Datasets are sourced and compiled by **skills** (see `.claude/skills/`) so that
acquiring a new dataset for a new question is a repeatable, low-effort flow.

**Live web app:** https://rolyntrotter.github.io/vibe-economics/

---

## Architecture at a glance

```
acquire-dataset  →  data/raw/      (skill: download from a source)
compile-dataset  →  data/processed/ (skill: raw → tidy parquet, registered in data/catalog.yaml)
analyze-economics →  backend/app/services/<name>/  (skill: pandas analysis + FastAPI endpoint)
build-widget     →  frontend/src/services/<Name>.jsx (skill: React widget)
```

- **`backend/`** — FastAPI app. One sub-package per service under `app/services/`.
  Shared dataset loading/caching in `app/core/`.
- **`frontend/`** — Vite + React PWA (installable on Android). Reusable widgets in
  `src/components/`, one screen per service in `src/services/`.
- **`data/`** — `raw/` (gitignored downloads), `processed/` (committed tidy
  parquet/csv), and `catalog.yaml` (the dataset registry: source, URL, license, key?).
- **`docs/tickets/`** — one markdown ticket per planned service (mirrored as GitHub Issues).
- **`.claude/skills/`** — the acquire → compile → analyze → widget flow.

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for the full design and roadmap,
and **[docs/datasets.md](docs/datasets.md)** for the catalog of known data sources.

---

## Quickstart (local dev)

```bash
# 1. Backend (Python 3.11+)
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt

# 2. Acquire + compile the reference dataset (Shiller historical returns)
cd backend
.venv/bin/python -m app.cli acquire shiller_returns      # downloads to data/raw/
.venv/bin/python -m app.cli compile shiller_returns      # writes data/processed/

# 3. Run the API
.venv/bin/uvicorn app.main:app --reload --port 8000

# 4. Frontend (Node 18+), in another terminal
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Or use the helper: `./scripts/dev.sh` (runs backend + frontend together).

---

## Deployed web app (GitHub Pages)

The frontend is published as a **fully static** web app at
**https://rolyntrotter.github.io/vibe-economics/**.

GitHub Pages can't run the Python backend, so deployed widgets compute
**client-side** from committed JSON snapshots in `frontend/public/data/`. The
FastAPI backend remains the tested source of truth for local dev; the
safe-withdrawal math is mirrored 1:1 in
`frontend/src/services/safeWithdrawalModel.js` (verified to reproduce the Python
results exactly).

- Deploy is automatic on push to `main` via `.github/workflows/deploy-pages.yml`.
  The first time, enable **Settings → Pages → Source: GitHub Actions**.
- The Vite `base` is `/vibe-economics/` for production builds, `/` for dev.
- Regenerate the static snapshots after recompiling a dataset:
  `backend/.venv/bin/python scripts/export_static_data.py`.

When a future service needs a live/large dataset that can't be snapshotted, host
the API separately and point the widget at it via `VITE_API_BASE`.

---

## Reference service: Safe Withdrawal Backtester

The first fully-built service (`backend/app/services/safe_withdrawal/` +
`frontend/src/services/SafeWithdrawal.jsx`) answers:

> For each retirement start-year in the past ~150 years, what was the **maximum
> constant inflation-adjusted withdrawal rate** that brought a portfolio to
> *exactly* \$0 at the end of a 30-year retirement — for an all-stock, 60/40, or
> three-fund allocation? (the "upper bound on the 4% rule")

The historical **minimum** of those per-cohort upper bounds is the empirically
"safe" rate to compare against the 4% rule of thumb. It is the **template** for
every other service: copy its shape (data loader → model → router → tests → widget).

## Services roadmap

| # | Service | Ticket | Issue | Status |
|---|---------|--------|-------|--------|
| 3 | Safe withdrawal backtester | [0003](docs/tickets/0003-safe-withdrawal-backtester.md) | #1 | **built (reference)** |
| 5 | Cost of living comparison | [0005](docs/tickets/0005-cost-of-living-comparison.md) | #2 | planned (flagship) |
| 2 | Subnational GDP comparison | [0002](docs/tickets/0002-subnational-gdp-comparison.md) | #3 | planned |
| 4 | Fed wealth & income trends | [0004](docs/tickets/0004-fed-wealth-income-trends.md) | #4 | planned |
| 1 | Currency circulation crossover | [0001](docs/tickets/0001-currency-circulation.md) | #5 | planned |
