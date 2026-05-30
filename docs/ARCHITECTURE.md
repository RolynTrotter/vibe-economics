# vibe-economics — Architecture & Roadmap

This document is the overall plan for the repo: what it is, how the pieces fit,
the conventions every service follows, and the order we build things in.

## Goal

Make it cheap to go from an economics question → a verifiable, interactive
answer on a phone. The flagship interaction is conversational:

> "Hey Claude, compare cost of living between Northern Virginia and Johor Bahru
> across rent, groceries, and healthcare. Use skills in vibe-economics to find
> and grab the datasets, produce a report, and make widgets I can verify in the
> browser."

For that to be a low-effort ask, the repo provides **reusable plumbing** so the
only novel work per question is the analysis itself.

## The four-stage flow (implemented as skills)

Every service is produced by the same pipeline. Each stage is a Claude skill in
`.claude/skills/`:

1. **`acquire-dataset`** — Given a question, identify authoritative,
   preferably key-free and ToS-clean sources; download raw files into
   `data/raw/<dataset_id>/`. Records provenance.
2. **`compile-dataset`** — Transform raw files into **tidy** parquet/csv in
   `data/processed/`, and register them in `data/catalog.yaml` (id, source, URL,
   license, columns, units, refresh command). Tidy = one observation per row,
   long format, explicit units.
3. **`analyze-economics`** — Build a service under
   `backend/app/services/<name>/`: a pure-Python `model.py` (pandas/numpy, no web
   concerns), a `data.py` loader, a FastAPI `router.py`, and `tests/`.
4. **`build-widget`** — Build `frontend/src/services/<Name>.jsx`: a mobile-first
   React widget that calls the endpoint and renders charts/tables/controls,
   reusing `src/components/`.

A skill can be run by Claude end-to-end in one conversation, or invoked stage by
stage. The reference service (safe withdrawal) was built by walking this flow and
is the worked example each skill points back to.

## Repo layout

```
vibe-economics/
├── data/
│   ├── catalog.yaml          # dataset registry (source of truth for what we have)
│   ├── raw/                  # downloaded source files (gitignored)
│   └── processed/            # tidy parquet/csv (committed → offline & reproducible)
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py           # FastAPI app; auto-discovers service routers
│   │   ├── cli.py            # `acquire` / `compile` / `list` dataset commands
│   │   ├── core/
│   │   │   ├── catalog.py    # load catalog.yaml, resolve paths
│   │   │   ├── datasets.py   # cached parquet loading helpers
│   │   │   └── sources/      # generic fetchers (http, world_bank, eurostat, ...)
│   │   └── services/
│   │       └── safe_withdrawal/   # reference service
│   └── tests/
├── frontend/
│   ├── package.json, vite.config.js, index.html
│   ├── public/manifest.webmanifest   # PWA (installable on Android)
│   └── src/
│       ├── api.js            # fetch wrapper pointed at the backend
│       ├── components/       # reusable widgets (charts, sliders, cards)
│       └── services/         # one screen per service
├── docs/
│   ├── ARCHITECTURE.md       # this file
│   ├── datasets.md           # human-readable catalog of known sources
│   └── tickets/              # one markdown ticket per service
└── .claude/skills/           # acquire / compile / analyze / build-widget
```

## Conventions

**Datasets**
- Every dataset has a stable `id` (snake_case) and an entry in `data/catalog.yaml`.
- Processed data is **tidy** and **committed** so services run offline and results
  are reproducible. Raw downloads are gitignored; the catalog records how to refetch.
- Prefer sources that are free, key-less, and license-clean. When a key is
  required, read it from an env var (never commit it) and note it in the catalog.
- Units are explicit (a `unit` column or documented column suffixes). Currency is
  noted (nominal vs real, base year).

**Backend**
- `model.py` is pure and testable — no FastAPI imports, no I/O beyond a passed-in
  DataFrame. `router.py` is thin: parse params → call model → return JSON.
- Pydantic models define request/response shapes.
- Each service ships at least one test that pins a known numeric result.

**Frontend**
- Mobile-first: single column, large tap targets, works on a phone in portrait.
- Widgets call the backend via `src/api.js`; the base URL is configurable
  (`VITE_API_BASE`).
- Reusable visual primitives live in `src/components/`; service screens compose them.
- It's a PWA so it can be "installed" to an Android home screen.

**Reports**
- Conversational analyses can emit a markdown report under `reports/` (gitignored
  by default unless you want to keep one) plus the widget for interactive checking.

## Roadmap / build order

1. **Foundation** (this session): repo scaffold, the four skills, dataset catalog,
   backend+frontend plumbing, dataset CLI.
2. **Reference service**: Safe Withdrawal Backtester — fully built end-to-end as the
   copyable template (ticket 0003).
3. **Flagship next**: Cost of Living comparison (ticket 0005) — exercises the
   acquire/compile skills hardest (multi-source, geographic entities).
4. Remaining tickets (0001, 0002, 0004) as needed.

## Open decisions / future work
- Auth: none for now (local/personal use). Add if ever deployed publicly.
- Deployment: currently local dev only. A `Dockerfile` + static frontend build
  can come later.
- Geographic entity resolution (city/region/country → dataset keys) is a shared
  need for several services; factor into `app/core/` once a second geo service exists.
- Caching of live API pulls (World Bank/Eurostat) with TTL in `data/raw/`.
