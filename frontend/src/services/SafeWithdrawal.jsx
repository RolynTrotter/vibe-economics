// Safe Withdrawal Backtester widget — the reference service screen.
// Shows the "upper bound on the 4% rule": for each retirement start year, the max
// constant real withdrawal that depletes the portfolio to exactly $0.
//
// The deployed app is static (GitHub Pages, no backend), so this computes in the
// browser from a committed snapshot (public/data/jst_returns.json) using
// safeWithdrawalModel.js — a 1:1 port of the tested Python model. The data has a
// real international equity sleeve, so the three-fund genuinely differs from a US
// 60/40.
import { useEffect, useMemo, useState } from "react";
import { loadDataset } from "../data.js";
import * as swm from "./safeWithdrawalModel.js";
import MetricCard from "../components/MetricCard.jsx";
import LineChart from "../components/LineChart.jsx";

const PRESETS = [
  { key: "all_stock", label: "100% US" },
  { key: "three_fund", label: "3-fund" },
  { key: "sixty_forty", label: "US 60 / 40" },
  { key: "custom", label: "Custom" },
];

const pct = (v) => `${(v * 100).toFixed(2)}%`;
const pct0 = (v) => `${Math.round(v * 100)}%`;

export default function SafeWithdrawal() {
  const [presetKey, setPresetKey] = useState("three_fund");
  // Custom controls: overall equity share, and intl share *within* equity.
  const [equity, setEquity] = useState(0.6);
  const [intlShare, setIntlShare] = useState(0.4);
  const [horizon, setHorizon] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const weights = useMemo(() => {
    if (presetKey !== "custom") return swm.PRESETS[presetKey];
    return {
      us: equity * (1 - intlShare),
      intl: equity * intlShare,
      bond: 1 - equity,
    };
  }, [presetKey, equity, intlShare]);

  useEffect(() => {
    loadDataset("jst_returns").then(setData).catch((e) => setError(e.message));
  }, []);

  // All computation is client-side and cheap; memoize on the inputs.
  const { summary, byYear } = useMemo(() => {
    if (!data) return { summary: null, byYear: null };
    return {
      summary: swm.summary(data.rows, horizon, weights),
      byYear: swm.swrByStartYear(data.rows, horizon, weights),
    };
  }, [data, horizon, weights]);

  const series = byYear
    ? [
        {
          label: "Max safe withdrawal (per start year)",
          color: "#64d2ff",
          points: byYear.map((p) => ({ x: p.start_year, y: p.swr })),
        },
      ]
    : [];

  return (
    <div>
      <div className="panel controls">
        <div>
          <div className="footnote" style={{ marginBottom: 6 }}>Allocation</div>
          <div className="seg">
            {PRESETS.map((p) => (
              <button
                key={p.key}
                className={presetKey === p.key ? "active" : ""}
                onClick={() => setPresetKey(p.key)}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="footnote" style={{ marginTop: 8 }}>
            US {pct0(weights.us)} · Intl {pct0(weights.intl)} · Bonds {pct0(weights.bond)}
          </div>
        </div>

        {presetKey === "custom" && (
          <>
            <label className="field">
              Equity (vs bonds) <span className="val">{pct(equity)}</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={equity}
                onChange={(e) => setEquity(parseFloat(e.target.value))}
              />
            </label>
            <label className="field">
              International share of equity <span className="val">{pct(intlShare)}</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={intlShare}
                onChange={(e) => setIntlShare(parseFloat(e.target.value))}
              />
            </label>
          </>
        )}

        <label className="field">
          Retirement horizon <span className="val">{horizon} years</span>
          <input
            type="range"
            min="10"
            max="50"
            step="1"
            value={horizon}
            onChange={(e) => setHorizon(parseInt(e.target.value, 10))}
          />
        </label>
      </div>

      {error && <div className="panel error">Error: {error}</div>}
      {!data && !error && <div className="panel loading">Loading data…</div>}

      {summary && (
        <>
          <div className="panel">
            <div className="cards">
              <MetricCard
                label="Empirical safe rate (worst cohort)"
                value={pct(summary.min_swr)}
                sub={`worst start year: ${summary.min_swr_start_year}`}
                tone={summary.min_swr >= 0.04 ? "good" : "bad"}
              />
              <MetricCard
                label="4% rule baseline"
                value={pct(summary.baseline_4pct_rule)}
                sub={
                  summary.min_swr >= 0.04
                    ? "every cohort beat 4%"
                    : "4% failed the worst cohort"
                }
                tone="warn"
              />
              <MetricCard
                label="Median upper bound"
                value={pct(summary.median_swr)}
                sub="typical perfect-hindsight max"
              />
              <MetricCard
                label="Cohorts ≥ 4%"
                value={pct(summary.share_at_least_4pct)}
                sub={`of ${summary.n_start_years} start years`}
                tone={summary.share_at_least_4pct >= 0.95 ? "good" : "warn"}
              />
            </div>
          </div>

          <div className="panel">
            <div className="chart-title">
              Upper bound on the 4% rule — max safe withdrawal by retirement start year
            </div>
            <LineChart
              series={series}
              refLines={[{ y: 0.04, label: "4% rule", color: "#ffd166" }]}
              yFormat={(v) => `${(v * 100).toFixed(1)}%`}
              xLabel="start year"
              yLabel="max real withdrawal rate"
              height={240}
            />
            <div className="footnote" style={{ marginTop: 8 }}>
              Each point is the largest constant inflation-adjusted withdrawal that
              would have brought a portfolio of US {pct0(weights.us)} / international{" "}
              {pct0(weights.intl)} / bonds {pct0(weights.bond)} to exactly $0 after{" "}
              {horizon} years — the perfect-hindsight ceiling. Where the blue line
              dips below the dashed 4% line, the 4% rule would have failed.
            </div>
          </div>
        </>
      )}

      {data && (
        <div className="panel footnote">
          Source: {data.source}. Data {data.first_year}–{data.last_year} ({data.n_years} yrs),{" "}
          {data.units}. {data.notes}
        </div>
      )}
    </div>
  );
}
