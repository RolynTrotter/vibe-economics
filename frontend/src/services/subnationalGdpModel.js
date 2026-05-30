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

// Which FUAs to punch out of one country, given the toggles. `metros` is that
// country's metros (sorted by GDP share, desc). If both toggles are on and the
// capital IS the largest (London, Paris, Tokyo), also drop the next-largest so two
// distinct metros come out.
export function selectRemovedMetros(metros, removeCapital, removeLargest) {
  const rows = [...metros].sort((a, b) => b.gdp_share_pct - a.gdp_share_pct);
  if (!rows.length) return [];
  const chosen = new Map();
  if (removeLargest) chosen.set(rows[0].code, rows[0]);
  if (removeCapital) {
    const cap = rows.find((r) => r.is_capital);
    if (cap) chosen.set(cap.code, cap);
  }
  if (removeCapital && removeLargest && chosen.size < 2) {
    for (const r of rows) if (!chosen.has(r.code)) { chosen.set(r.code, r); break; }
  }
  return [...chosen.values()];
}

// Country-level ladder with each country's selected metro(s) punched out.
// `countries` is the hinterland block from the snapshot.
export function hinterlandTable(countries, basis, removeCapital, removeLargest) {
  const spec = BASES[basis];
  if (!spec) throw new Error(`Unknown basis '${basis}'`);
  const rows = [];
  for (const c of countries) {
    const removed = selectRemovedMetros(c.metros, removeCapital, removeLargest);
    const share = removed.reduce((s, r) => s + r.gdp_share_pct, 0) / 100;
    const popRemoved = removed.reduce((s, r) => s + (r.population || 0), 0);
    const restPop = c.nat_population - popRemoved;
    if (restPop <= 0 || share >= 0.999) continue;
    const restNom = c.nat_gdp_nominal_usd != null ? c.nat_gdp_nominal_usd * (1 - share) : null;
    const restPpp = c.nat_gdp_ppp_usd * (1 - share);
    let value;
    if (basis === "nominal") value = restNom;
    else if (basis === "ppp") value = restPpp;
    else value = restPpp / restPop;
    if (value == null) continue;
    rows.push({
      id: c.iso3, entity_id: c.iso3, name: c.name, kind: "country",
      parent: c.iso3, region: c.region, value, year: c.year,
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
