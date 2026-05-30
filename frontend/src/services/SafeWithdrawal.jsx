// Safe Withdrawal Backtester widget — the reference service screen.
// Shows the "upper bound on the 4% rule": for each retirement start year, the max
// constant real withdrawal that depletes the portfolio to exactly $0.
import { useEffect, useState } from "react";
import { api } from "../api.js";
import MetricCard from "../components/MetricCard.jsx";
import LineChart from "../components/LineChart.jsx";

const PRESETS = [
  { key: "all_stock", label: "100% stock" },
  { key: "three_fund", label: "3-fund (~70/30)" },
  { key: "sixty_forty", label: "60 / 40" },
  { key: "custom", label: "Custom" },
];

const pct = (v) => `${(v * 100).toFixed(2)}%`;

export default function SafeWithdrawal() {
  const [presetKey, setPresetKey] = useState("sixty_forty");
  const [stock, setStock] = useState(0.6);
  const [horizon, setHorizon] = useState(30);
  const [summary, setSummary] = useState(null);
  const [byYear, setByYear] = useState(null);
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  // Resolve the stock weight from the active preset (custom uses the slider).
  const presetWeights = { all_stock: 1.0, three_fund: 0.7, sixty_forty: 0.6 };
  const stockWeight = presetKey === "custom" ? stock : presetWeights[presetKey];

  useEffect(() => {
    api("/api/safe-withdrawal/meta").then(setMeta).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    const params = { horizon, stock: stockWeight };
    Promise.all([
      api("/api/safe-withdrawal/summary", params),
      api("/api/safe-withdrawal/by-year", params),
    ])
      .then(([s, b]) => {
        if (!alive) return;
        setSummary(s);
        setByYear(b);
      })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [stockWeight, horizon]);

  const series = byYear
    ? [
        {
          label: "Max safe withdrawal (per start year)",
          color: "#64d2ff",
          points: byYear.points.map((p) => ({ x: p.start_year, y: p.swr })),
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
        </div>

        {presetKey === "custom" && (
          <label className="field">
            Stock weight <span className="val">{pct(stock)}</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={stock}
              onChange={(e) => setStock(parseFloat(e.target.value))}
            />
          </label>
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
      {loading && !summary && <div className="panel loading">Computing…</div>}

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
              would have brought a {Math.round(stockWeight * 100)}/
              {Math.round((1 - stockWeight) * 100)} portfolio to exactly $0 after{" "}
              {horizon} years — the perfect-hindsight ceiling. Where the blue line
              dips below the dashed 4% line, the 4% rule would have failed.
            </div>
          </div>
        </>
      )}

      {meta && (
        <div className="panel footnote">
          Source: {meta.source}. Data {meta.first_year}–{meta.last_year} ({meta.n_years} yrs),{" "}
          {meta.units}. {meta.notes}
        </div>
      )}
    </div>
  );
}
