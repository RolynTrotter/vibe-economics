// Client-side mirror of backend/app/services/subnational_gdp/model.py.
// The deployed app is static, so the ranking/matcher run in the browser from the
// committed snapshot (public/data/subnational_gdp.json). Kept 1:1 with the tested
// Python model so the deployed numbers equal the backend's.

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
  if (kinds) rows = rows.filter((e) => kinds.includes(e.kind));
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
