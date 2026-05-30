// Client-side port of backend/app/services/safe_withdrawal/model.py.
//
// The deployed app (GitHub Pages) is static — there is no FastAPI backend — so the
// safe-withdrawal math runs in the browser against a committed JSON snapshot
// (public/data/shiller_returns.json). The Python model remains the tested source
// of truth for local dev; this file mirrors it 1:1. Keep them in sync.
//
// "SWR" = the upper bound on the 4% rule: the max constant inflation-adjusted
// withdrawal (as a fraction of the initial balance) that depletes the portfolio
// to exactly $0 at the end of the horizon, withdrawing at the start of each year.

export const RULE_OF_THUMB = 0.04;

export const PRESETS = {
  all_stock: 1.0,
  three_fund: 0.7,
  sixty_forty: 0.6,
};

// rows: [[year, stock_return, bond_return, inflation], ...] (already sorted by year)
export function realReturns(rows, stockWeight) {
  const sw = stockWeight;
  return rows.map(([year, stock, bond, infl]) => {
    const nominal = sw * stock + (1 - sw) * bond;
    const real = (1 + nominal) / (1 + infl) - 1;
    return { year, real };
  });
}

// w = Π(1+r) / Σ_k Π_{t>=k}(1+r)  — closed form for the depleting-to-zero rate.
export function maxSwrForWindow(realSeq) {
  const n = realSeq.length;
  const growth = realSeq.map((r) => 1 + r);
  // suffixProd[k] = product of growth[k..n-1]
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

export function swrByStartYear(rows, horizon, stockWeight) {
  const rr = realReturns(rows, stockWeight);
  const out = [];
  for (let i = 0; i + horizon <= rr.length; i++) {
    const window = rr.slice(i, i + horizon).map((d) => d.real);
    out.push({ start_year: rr[i].year, swr: maxSwrForWindow(window) });
  }
  return out;
}

export function portfolioPath(rows, startYear, horizon, stockWeight, rate) {
  const rr = realReturns(rows, stockWeight);
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

export function summary(rows, horizon, stockWeight) {
  const byYear = swrByStartYear(rows, horizon, stockWeight);
  const swrs = byYear.map((d) => d.swr);
  let minIdx = 0;
  let maxIdx = 0;
  for (let i = 1; i < swrs.length; i++) {
    if (swrs[i] < swrs[minIdx]) minIdx = i;
    if (swrs[i] > swrs[maxIdx]) maxIdx = i;
  }
  const sorted = [...swrs].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median =
    sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  return {
    horizon,
    stock_weight: stockWeight,
    n_start_years: byYear.length,
    first_start_year: byYear[0].start_year,
    last_start_year: byYear[byYear.length - 1].start_year,
    baseline_4pct_rule: RULE_OF_THUMB,
    min_swr: swrs[minIdx],
    min_swr_start_year: byYear[minIdx].start_year,
    median_swr: median,
    max_swr: swrs[maxIdx],
    max_swr_start_year: byYear[maxIdx].start_year,
    share_at_least_4pct:
      swrs.filter((s) => s >= RULE_OF_THUMB).length / swrs.length,
  };
}
