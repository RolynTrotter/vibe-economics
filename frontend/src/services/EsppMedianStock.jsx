// ESPP / median-stock — how the *typical* (median) S&P 500 stock does over a
// one-year hold vs the index, and whether an ESPP discount is worth being forced
// to hold a single employer stock for a year before you can sell.
//
// Deployed app is static, so this reads a committed snapshot
// (public/data/espp_median_stock.json) precomputed by the tested Python model.
// The discount slider snaps to 1% and reads the matching pooled distribution that
// was precomputed for every discount 0–30%.
import { useEffect, useMemo, useState } from "react";
import { loadDataset } from "../data.js";
import MetricCard from "../components/MetricCard.jsx";
import LineChart from "../components/LineChart.jsx";

const STOCK = "#ffd166"; // median single stock
const INDEX = "#64d2ff"; // the index (SPY, total return)
const ESPP = "#7CFFB2"; // discounted-stock outcome

const pct = (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
const signPct = (v) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);

export default function EsppMedianStock() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [discountPct, setDiscountPct] = useState(15); // integer %, matches snapshot keys

  useEffect(() => {
    loadDataset("espp_median_stock").then(setData).catch((e) => setError(e.message));
  }, []);

  const pooled = useMemo(() => {
    if (!data) return null;
    return data.by_discount[String(discountPct)] ?? null;
  }, [data, discountPct]);

  const yearSeries = useMemo(() => {
    if (!data) return [];
    return [
      {
        label: "Median stock",
        color: STOCK,
        points: data.by_year.map((r) => ({ x: r.year, y: r.median_stock })),
      },
      {
        label: "Index (SPY, total return)",
        color: INDEX,
        points: data.by_year.map((r) => ({ x: r.year, y: r.index })),
      },
    ];
  }, [data]);

  const d = discountPct / 100;

  return (
    <div>
      <div className="panel">
        <div className="footnote" style={{ marginBottom: 8 }}>
          The index is carried by a few huge winners, so the <b>typical</b> stock is
          the <b>median</b> — not the average. This asks how the median S&P 500 stock
          did over each one-year hold vs the index, then whether an ESPP discount
          covers the gap (and the single-stock risk) when a plan locks you in for a
          year.
        </div>
        <label className="field">
          ESPP purchase discount <span className="val">{discountPct}%</span>
          <input
            type="range"
            min="0"
            max="30"
            step="1"
            value={discountPct}
            onChange={(e) => setDiscountPct(parseInt(e.target.value, 10))}
          />
        </label>
        <div className="footnote" style={{ marginTop: 4 }}>
          Buying at a {discountPct}% discount is a one-time head start of{" "}
          <b>{pooled ? signPct(pooled.espp_head_start) : "—"}</b> on your cash —
          you then ride one stock for a year: return ={" "}
          <code>(1 + stock) / (1 − {d.toFixed(2)}) − 1</code>.
        </div>
      </div>

      {error && <div className="panel error">Error: {error}</div>}
      {!data && !error && <div className="panel loading">Loading data…</div>}

      {pooled && (
        <>
          <div className="panel">
            <div className="cards">
              <MetricCard
                label="Median stock vs index (1-yr)"
                value={signPct(pooled.median_excess_vs_index)}
                sub="typical single-stock gap, no discount"
                tone={pooled.median_excess_vs_index >= 0 ? "good" : "bad"}
              />
              <MetricCard
                label="Stocks that beat the index"
                value={pct(pooled.pct_beat_index)}
                sub="share of stock-years (no discount)"
              />
              <MetricCard
                label={`ESPP-stock beats index (${discountPct}% off)`}
                value={pct(pooled.espp_pct_beat_index)}
                sub="discount applied, 1-yr hold"
                tone={pooled.espp_pct_beat_index >= 0.5 ? "good" : "warn"}
              />
              <MetricCard
                label={`Lose money even with ${discountPct}% off`}
                value={pct(pooled.espp_pct_underwater)}
                sub={`stock fell more than ${discountPct}%`}
                tone={pooled.espp_pct_underwater <= 0.15 ? "good" : "warn"}
              />
              <MetricCard
                label="Median ESPP return on cash"
                value={signPct(pooled.espp_median_return)}
                sub="typical 1-yr outcome with discount"
                tone="good"
              />
              <MetricCard
                label="Any single stock falls in a year"
                value={pct(pooled.pct_negative)}
                sub="vs the diversified index's far rarer down years"
                tone="warn"
              />
            </div>
          </div>

          <div className="panel">
            <div className="chart-title">
              Median S&P 500 stock vs the index — one-year total return by year
            </div>
            <LineChart
              series={yearSeries}
              refLines={[{ y: 0, label: "0%", color: "#7c89b0" }]}
              yFormat={(v) => `${(v * 100).toFixed(0)}%`}
              xLabel="year"
              yLabel="1-yr total return"
              height={250}
            />
            <div className="footnote" style={{ marginTop: 8 }}>
              The median stock tracks the index closely year to year — over a single
              year the much-discussed "most stocks lag the index" skew is mild
              (it compounds over <i>many</i> years, not one). The gap between them is
              small next to a {discountPct}% discount. Note the median stock is
              effectively equal-weighted; the index is cap-weighted, so the recent
              mega-cap years (2019, 2023–25) show the index pulling ahead.
            </div>
          </div>

          <div className="panel verdict">
            <div className="chart-title">Is the ESPP worth it under a 1-year hold?</div>
            <p style={{ margin: "6px 0 0", lineHeight: 1.5 }}>{data.verdict}</p>
          </div>
        </>
      )}

      {data && (
        <div className="panel footnote">
          <b>Source:</b> {data.source} Data {data.first_year}–{data.last_year}.{" "}
          {data.definition}
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {data.caveats.map((c, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
