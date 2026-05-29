---
name: analyze-economics
description: >
  Build a vibe-economics backend service: a pure-Python pandas/numpy analysis
  plus a FastAPI endpoint that exposes it as JSON. Use after a tidy dataset
  exists in data/processed/ and you need to compute the answer to an economics
  question (backtest, comparison, time series, distribution) and serve it.
---

# analyze-economics

Stage 3 of the four-stage flow. Your job: tidy data → the computed answer,
exposed as a clean JSON API the frontend can call.

## Service shape (copy the reference service)
Create `backend/app/services/<name>/` with:

- **`data.py`** — load the processed dataset(s) via `app/core/datasets.py`
  (cached). Include the dataset's `compile_*` here if the service owns it.
- **`model.py`** — **pure** analysis: functions that take a DataFrame + params and
  return numbers/DataFrames. **No FastAPI imports, no I/O.** This is what tests
  hit. Keep the economics here.
- **`router.py`** — thin FastAPI `APIRouter`: Pydantic request/response models,
  parse params → call `model` → return JSON. Mounted automatically by `main.py`.
- **`tests/test_<name>.py`** — pin at least one known numeric result so the
  analysis can't silently drift.

## Conventions
- Keep `model.py` deterministic and side-effect-free; pass data in, return data out.
- Validate/clamp params (e.g. allocation weights sum to 1, year in range).
- Return tidy JSON: arrays of records or {x:[], y:[]} series the frontend charts.
- Document units in the response (e.g. real vs nominal, %).
- Add the router to whatever discovery `app/main.py` uses (it auto-includes
  `services/*/router.py:router`).

## Worked example
`app/services/safe_withdrawal/`:
- `data.py` loads `shiller_returns.parquet`;
- `model.py` has `max_safe_withdrawal_rate(returns_df, start_year, horizon, weights)`
  — pure, tested;
- `router.py` exposes `GET /api/safe-withdrawal/...`;
- `tests/test_safe_withdrawal.py` pins a known SWR.

## Next stage
Hand off to **build-widget** to put a phone-friendly UI on the endpoint.
