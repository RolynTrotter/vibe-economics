// Client-side port of backend/app/services/safe_withdrawal/model.py.
//
// The deployed app (GitHub Pages) is static — there is no FastAPI backend — so the
// safe-withdrawal math runs in the browser against a committed JSON snapshot
// (public/data/jst_returns.json). The Python model remains the tested source of
// truth for local dev; this file mirrors it 1:1. Keep them in sync.
//
// "SWR" = the upper bound on the 4% rule: the max constant inflation-adjusted
// withdrawal (fraction of the initial balance) that depletes the portfolio to
// exactly $0 at the end of the horizon, withdrawing at the start of each year.
//
// Allocations are three-asset: { us, intl, bond } (us/intl are equity sleeves).
// A real international sleeve makes the three-fund genuinely differ from US 60/40.

export const RULE_OF_THUMB = 0.04;

export const PRESETS = {
  all_stock: { us: 1.0, intl: 0.0, bond: 0.0 },
  three_fund: { us: 0.36, intl: 0.24, bond: 0.4 },
  sixty_forty: { us: 0.6, intl: 0.0, bond: 0.4 },
};

const ASSETS = ["us", "intl", "bond"];

export function normalizeWeights(weights) {
  const w = {};
  for (const a of ASSETS) w[a] = Number(weights[a] || 0);
  if (ASSETS.some((a) => w[a] < 0)) throw new Error("weights must be non-negative");
  const total = ASSETS.reduce((s, a) => s + w[a], 0);
  if (total <= 0) throw new Error("weights must sum to a positive number");
  if (Math.abs(total - 1) > 1e-9) for (const a of ASSETS) w[a] /= total;
  return w;
}

// rows: [[year, us_stock, intl_stock, bond, inflation], ...] (sorted by year)
export function realReturns(rows, weights) {
  const w = normalizeWeights(weights);
  return rows.map(([year, us, intl, bond, infl]) => {
    const nominal = w.us * us + w.intl * intl + w.bond * bond;
    const real = (1 + nominal) / (1 + infl) - 1;
    return { year, real };
  });
}

// w = Π(1+r) / Σ_k Π_{t>=k}(1+r)  — closed form for the depleting-to-zero rate.
export function maxSwrForWindow(realSeq) {
  const n = realSeq.length;
  const growth = realSeq.map((r) => 1 + r);
  const suffixProd = new Array(n);
  let acc = 1;
  for (let k = n - 1; k >= 0; k--) {
    acc *= growth[k];
    suffixProd[k] = acc;
  }
  const totalGrowth = suffixProd[0];
  const denom = suffixProd.reduce((a, b) => a + b, 0);
  return totalGrowth / denom;
}

export function swrByStartYear(rows, horizon, weights) {
  const rr = realReturns(rows, weights);
  const out = [];
  for (let i = 0; i + horizon <= rr.length; i++) {
    const window = rr.slice(i, i + horizon).map((d) => d.real);
    out.push({ start_year: rr[i].year, swr: maxSwrForWindow(window) });
  }
  return out;
}

export function portfolioPath(rows, startYear, horizon, weights, rate) {
  const rr = realReturns(rows, weights);
  const idx = rr.findIndex((d) => d.year === startYear);
  if (idx < 0) throw new Error(`start_year ${startYear} not in data range`);
  if (idx + horizon > rr.length)
    throw new Error(`Not enough data for a ${horizon}-year window starting ${startYear}`);
  let balance = 1.0;
  const path = [];
  for (let h = 0; h < horizon; h++) {
    const startBal = balance;
    balance = (balance - rate) * (1 + rr[idx + h].real);
    path.push({
      year: rr[idx + h].year,
      balance_start: startBal,
      withdrawal: rate,
      balance_end: balance,
    });
  }
  return path;
}

export function summary(rows, horizon, weights) {
  const w = normalizeWeights(weights);
  const byYear = swrByStartYear(rows, horizon, w);
  const swrs = byYear.map((d) => d.swr);
  let minIdx = 0;
  let maxIdx = 0;
  for (let i = 1; i < swrs.length; i++) {
    if (swrs[i] < swrs[minIdx]) minIdx = i;
    if (swrs[i] > swrs[maxIdx]) maxIdx = i;
  }
  const sorted = [...swrs].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  return {
    horizon,
    weights: w,
    n_start_years: byYear.length,
    first_start_year: byYear[0].start_year,
    last_start_year: byYear[byYear.length - 1].start_year,
    baseline_4pct_rule: RULE_OF_THUMB,
    min_swr: swrs[minIdx],
    min_swr_start_year: byYear[minIdx].start_year,
    median_swr: median,
    max_swr: swrs[maxIdx],
    max_swr_start_year: byYear[maxIdx].start_year,
    share_at_least_4pct: swrs.filter((s) => s >= RULE_OF_THUMB).length / swrs.length,
  };
}
