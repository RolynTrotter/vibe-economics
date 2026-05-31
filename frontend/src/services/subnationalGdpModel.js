// Client-side mirror of backend/app/services/subnational_gdp/model.py.
// The deployed app is static, so the ranking/matcher run in the browser from the
// committed snapshot (public/data/subnational_gdp.json). Kept 1:1 with the tested
// Python model so the deployed numbers equal the backend's.

// Dropped from the per-capita ranking only: DC's GDP-per-capita is a commuter
// artifact (metro-wide output ÷ DC residents). Mirrors PER_CAPITA_EXCLUDE in
// the Python model. Excluded until the metro-aware treatment lands.
export const PER_CAPITA_EXCLUDE = new Set(["US-DC"]);

export const BASES = {
  nominal: {
    column: "gdp_nominal_usd",
    perCapita: false,
    label: "Total GDP (nominal)",
    blurb: "GDP at market exchange rates — the headline size of the economy.",
  },
  ppp: {
    column: "gdp_ppp_usd",
    perCapita: false,
    label: "Total GDP (PPP)",
    blurb:
      "GDP adjusted for purchasing power (international $). US-state figures use " +
      "nominal USD as a PPP proxy (US ≈ PPP base).",
  },
  per_capita: {
    column: "gdp_ppp_usd",
    perCapita: true,
    label: "GDP per capita (PPP)",
    blurb: "PPP GDP divided by population — a living-standards lens.",
  },
};

// Value for one entity on a basis, or null when inputs are missing.
export function basisValue(e, basis) {
  const spec = BASES[basis];
  if (!spec) throw new Error(`Unknown basis '${basis}'`);
  const v = e[spec.column];
  if (v == null) return null;
  if (spec.perCapita) {
    if (!e.population || e.population <= 0) return null;
    return v / e.population;
  }
  return v;
}

// All entities sorted desc by basis, with a dense 1-based rank. `kinds` optionally
// filters to e.g. ["state","country"]. Entities with no value on the basis drop out.
export function rankedTable(entities, basis, kinds = null) {
  let rows = entities
    .map((e) => ({ ...e, value: basisValue(e, basis) }))
    .filter((e) => e.value != null);
  if (basis === "per_capita") rows = rows.filter((e) => !PER_CAPITA_EXCLUDE.has(e.id || e.entity_id));
  if (kinds) rows = rows.filter((e) => kinds.includes(e.kind));
  rows.sort((a, b) => b.value - a.value);
  rows.forEach((r, i) => (r.rank = i + 1));
  return rows;
}

// --- Metro punch-out ("hinterland" comparison) — mirrors model.py (ticket 0008) ---

// Which metros to punch out of one place, given the toggles. Each checked toggle
// nominates one metro (largest by GDP share, capital, richest by per-capita); when
// picks coincide each falls to the next-best in its ranking and any shortfall is
// filled by next-largest GDP, so #distinct removed == #toggles checked.
export function selectRemovedMetros(metros, removeCapital, removeLargest, removeRichest = false) {
  const rows = [...metros];
  if (!rows.length) return [];
  const byGdp = [...rows].sort((a, b) => b.gdp_share_pct - a.gdp_share_pct);
  const byPc = rows.filter((r) => r.per_capita).sort((a, b) => b.per_capita - a.per_capita);
  const nTargets = (removeCapital ? 1 : 0) + (removeLargest ? 1 : 0) + (removeRichest ? 1 : 0);
  const chosen = new Map();
  if (removeLargest) {
    const pick = byGdp.find((r) => !chosen.has(r.code));
    if (pick) chosen.set(pick.code, pick);
  }
  if (removeCapital) {
    const cap = rows.find((r) => r.is_capital);
    if (cap) chosen.set(cap.code, cap);
  }
  if (removeRichest) {
    const pick = byPc.find((r) => !chosen.has(r.code));
    if (pick) chosen.set(pick.code, pick);
  }
  for (const r of byGdp) {
    if (chosen.size >= nTargets) break;
    if (!chosen.has(r.code)) chosen.set(r.code, r);
  }
  return [...chosen.values()];
}

// A place whose residual after removal is below this fraction of the whole has no
// meaningful hinterland (e.g. New Jersey) — dropped rather than shown unstable.
export const MIN_RESIDUAL_FRACTION = 0.12;

// Ladder of `places` (countries and/or US states) with each one's selected metro(s)
// punched out. Mirrors model.hinterland_table. `kinds` optionally filters by kind.
export function hinterlandTable(places, basis, removeCapital, removeLargest, removeRichest = false, kinds = null) {
  const spec = BASES[basis];
  if (!spec) throw new Error(`Unknown basis '${basis}'`);
  const rows = [];
  for (const p of places) {
    if (kinds && !kinds.includes(p.kind)) continue;
    const removed = selectRemovedMetros(p.metros, removeCapital, removeLargest, removeRichest);
    const share = removed.reduce((s, r) => s + r.gdp_share_pct, 0) / 100;
    const popRemoved = removed.reduce((s, r) => s + (r.population || 0), 0);
    const restPop = p.nat_population - popRemoved;
    if (restPop <= MIN_RESIDUAL_FRACTION * p.nat_population || share >= 1 - MIN_RESIDUAL_FRACTION) continue;
    const restNom = p.nat_gdp_nominal_usd != null ? p.nat_gdp_nominal_usd * (1 - share) : null;
    const restPpp = p.nat_gdp_ppp_usd * (1 - share);
    let value;
    if (basis === "nominal") value = restNom;
    else if (basis === "ppp") value = restPpp;
    else value = restPpp / restPop;
    if (value == null) continue;
    rows.push({
      id: p.id, entity_id: p.id, name: p.name, kind: p.kind,
      parent: p.kind === "state" ? "USA" : p.id, region: p.region, value, year: p.year,
      removed: removed.map((r) => r.name), removed_share: share,
    });
  }
  rows.sort((a, b) => b.value - a.value);
  rows.forEach((r, i) => (r.rank = i + 1));
  return rows;
}

// For one entity, the `among`-kind neighbours nearest in basis value.
export function nearest(entities, entityId, basis, n = 3, among = "country") {
  const table = rankedTable(entities, basis);
  const target = table.find((e) => e.entity_id === entityId || e.id === entityId);
  if (!target) return null;
  const id = target.entity_id || target.id;
  let pool = table.filter((e) => (e.entity_id || e.id) !== id);
  if (among !== "any") pool = pool.filter((e) => e.kind === among);
  pool = pool
    .map((e) => ({ ...e, distance: Math.abs(e.value - target.value) }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, n);
  return { entity: target, basis, nearest: pool };
}
