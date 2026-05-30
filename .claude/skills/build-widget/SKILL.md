---
name: build-widget
description: >
  Build a mobile-first React widget (Vite PWA) for a vibe-economics service so
  findings can be explored and verified on an Android phone in the browser. Use
  after a backend service/endpoint exists and you want an interactive UI:
  charts, tables, sliders, comparison cards.
---

# build-widget

Stage 4 of the four-stage flow. Your job: turn a JSON endpoint into a
phone-friendly interactive widget.

## Steps
1. Add an API helper in `frontend/src/api.js` (or call the generic `api()` wrapper)
   pointed at the service endpoint. Base URL comes from `VITE_API_BASE`.
2. Create `frontend/src/services/<Name>.jsx` — the service screen. Compose
   reusable primitives from `frontend/src/components/` (charts, sliders, cards,
   tables). Add new reusable primitives there if they'll be used by >1 service.
3. Register the screen in `frontend/src/App.jsx` (the simple router/menu).
4. Make it **mobile-first**: single column, large tap targets, readable at phone
   width in portrait, controls (sliders/selects) usable with a thumb.
5. Show the units and source so a finding is verifiable (e.g. "real, CPI-adjusted",
   "Shiller data 1871–").

## Conventions
- Keep data-fetching in a hook/effect; render loading + error states.
- Charts: keep them simple and legible on a small screen; label axes & units.
- Don't reimplement primitives that exist in `components/` — reuse them.
- The app is a PWA (`public/manifest.webmanifest`), installable to a home screen.

## Worked example
`frontend/src/services/SafeWithdrawal.jsx`:
- allocation preset selector (all-stock / 60-40 / three-fund) + sliders,
- start-year and horizon controls,
- a line chart of the safe withdrawal rate by start year (reusing `LineChart`),
- a results card (reusing `MetricCard`),
all calling `GET /api/safe-withdrawal/*` through `src/api.js`.

## Verify
Run `npm run dev` (or `npm run build`) and confirm the widget renders, fetches,
and updates when controls change. For a conversational task, this is how the user
verifies your findings.
