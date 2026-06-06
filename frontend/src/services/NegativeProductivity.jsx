// Negative Productivity — a unified tab for value-destruction lenses (ticket 0010).
//
// LENS 1 (built): "Localized inflation" — relative-price dispersion across the six
// CPI major groups. A supply shock to one sector, plus reallocation frictions that
// keep incomes (and demand) stuck in the now-lower-value activity, shows up as a
// widening *spread* of inflation rates across sectors rather than a uniform rise.
// Ball & Mankiw (1995): that cross-sectional dispersion/skew co-moves with headline
// inflation. Future lenses (zombie firms, value subtraction) attach as more sub-tabs.
//
// Deployed app is static, so this reads a committed snapshot
// (public/data/negative_productivity_inflation.json) precomputed by the tested
// Python model — no client-side recompute needed.
import { useEffect, useMemo, useState } from "react";
import { loadDataset } from "../data.js";
import MetricCard from "../components/MetricCard.jsx";
import LineChart from "../components/LineChart.jsx";

const LENSES = [
  { key: "inflation", label: "Localized inflation", ready: true },
  { key: "zombies", label: "Zombie firms", ready: false },
  { key: "value_sub", label: "Value subtraction", ready: false },
];

const HOT = "#ff7b6b";
const COLD = "#64d2ff";
const pp = (v) => (v == null ? "—" : `${v >= 0 ? "" : ""}${v.toFixed(1)}%`);

export default function NegativeProductivity() {
  const [lens, setLens] = useState("inflation");
  return (
    <div>
      <div className="panel" style={{ paddingBottom: 10 }}>
        <div className="footnote" style={{ marginBottom: 6 }}>
          Lenses on activity that subtracts value. Tracking it from public data, one at a time.
        </div>
        <div className="seg">
          {LENSES.map((l) => (
            <button
              key={l.key}
              className={lens === l.key ? "active" : ""}
              disabled={!l.ready}
              onClick={() => l.ready && setLens(l.key)}
              title={l.ready ? "" : "Planned — see ticket 0010"}
            >
              {l.label}
              {l.ready ? "" : " ·soon"}
            </button>
          ))}
        </div>
      </div>
      {lens === "inflation" && <InflationLens />}
    </div>
  );
}

function InflationLens() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [secondary, setSecondary] = useState("dispersion"); // dispersion | spread
  const [idx, setIdx] = useState(null); // selected month index into series

  useEffect(() => {
    loadDataset("negative_productivity_inflation")
      .then((d) => {
        setData(d);
        setIdx(d.series.length - 1); // default to latest month
      })
      .catch((e) => setError(e.message));
  }, []);

  const series = data?.series ?? [];
  const sel = idx != null ? series[idx] : null;
  const selBreakdown = data && sel ? data.by_month[sel.label] ?? [] : [];

  const charts = useMemo(() => {
    if (!series.length) return [];
    const headline = {
      label: "Headline inflation (All items)",
      color: "#9fb0d8",
      points: series.filter((r) => r.headline != null).map((r) => ({ x: r.t, y: r.headline })),
    };
    const secMeta =
      secondary === "spread"
        ? { label: "Spread (hottest − coldest)", color: "#ffd166", key: "spread" }
        : { label: "Dispersion (cross-sector std dev)", color: HOT, key: "dispersion" };
    const sec = {
      label: secMeta.label,
      color: secMeta.color,
      points: series.map((r) => ({ x: r.t, y: r[secMeta.key] })),
    };
    return [headline, sec];
  }, [series, secondary]);

  if (error) return <div className="panel error">Error: {error}</div>;
  if (!data) return <div className="panel loading">Loading CPI data…</div>;

  // Supply-shock signature: high dispersion AND positive skew (a few categories
  // spiking up). Used only to tone the headline cards.
  const hotSignature = sel && sel.dispersion >= 3 && sel.skew > 0.5;
  const maxAbs = Math.max(1e-6, ...selBreakdown.map((c) => Math.abs(c.yoy)));
  const sortedCats = [...selBreakdown].sort((a, b) => b.yoy - a.yoy);

  return (
    <div>
      {sel && (
        <div className="panel">
          <div className="cards">
            <MetricCard
              label={`Headline inflation · ${sel.label}`}
              value={pp(sel.headline)}
              sub="All-items CPI, 12-month change"
              tone={sel.headline >= 4 ? "bad" : sel.headline >= 2.5 ? "warn" : "good"}
            />
            <MetricCard
              label="Dispersion across sectors"
              value={pp(sel.dispersion)}
              sub="std dev of the six groups' YoY"
              tone={sel.dispersion >= 3 ? "bad" : sel.dispersion >= 1.8 ? "warn" : "good"}
            />
            <MetricCard
              label="Skew"
              value={sel.skew >= 0 ? `+${sel.skew.toFixed(2)}` : sel.skew.toFixed(2)}
              sub={sel.skew > 0.3 ? "a few sectors spiking up" : sel.skew < -0.3 ? "a few sectors falling" : "broadly balanced"}
              tone={hotSignature ? "bad" : undefined}
            />
            <MetricCard
              label="Hottest vs coldest"
              value={`${sel.spread.toFixed(1)}pp`}
              sub={`${sel.hottest} ↔ ${sel.coldest}`}
            />
          </div>
          {hotSignature && (
            <div className="footnote" style={{ marginTop: 10, color: HOT }}>
              ⚠ Supply-shock signature: wide dispersion with positive skew — inflation
              concentrated in a few sectors, not broad-based.
            </div>
          )}
        </div>
      )}

      <div className="panel">
        <div className="chart-title">
          Headline inflation vs cross-sector dispersion, 1968–{data.last?.slice(0, 4)}
        </div>
        <div className="seg" style={{ marginBottom: 8 }}>
          {[
            ["dispersion", "Dispersion"],
            ["spread", "Spread"],
          ].map(([k, lab]) => (
            <button key={k} className={secondary === k ? "active" : ""} onClick={() => setSecondary(k)}>
              {lab}
            </button>
          ))}
        </div>
        <LineChart
          series={charts}
          refLines={[{ y: 0, label: "", color: "#2a3454" }]}
          yFormat={(v) => `${v.toFixed(0)}%`}
          xLabel="year"
          yLabel="percentage points"
          height={240}
        />
        <div className="episodes">
          <span className="footnote" style={{ alignSelf: "center", marginRight: 4 }}>
            Jump to a supply shock:
          </span>
          {data.episodes.map((ep) => (
            <button
              key={ep.label}
              className="seg-btn"
              onClick={() => setIdx(nearestIdx(series, (ep.start + ep.end) / 2))}
              style={{ border: "1px solid var(--border)", borderRadius: 6, background: "transparent", color: "var(--muted)" }}
            >
              {ep.label}
            </button>
          ))}
        </div>
        <div className="footnote" style={{ marginTop: 8 }}>
          The grey line is headline CPI inflation; the coloured line is how widely the
          six major groups' inflation rates were spread that month. They spike together
          in 1974, 1980 and 2021–22 — supply shocks show up as <em>localized</em>
          inflation (a few sectors), not a uniform rise.
        </div>
      </div>

      {sel && (
        <div className="panel">
          <div className="chart-title">Where inflation sat that month — {sel.label}</div>
          <label className="field">
            Month <span className="val">{sel.label}</span>
            <input
              type="range"
              min="0"
              max={series.length - 1}
              step="1"
              value={idx}
              onChange={(e) => setIdx(parseInt(e.target.value, 10))}
            />
          </label>
          <div className="ibars">
            {sortedCats.map((c) => {
              const half = (Math.abs(c.yoy) / maxAbs) * 50;
              const positive = c.yoy >= 0;
              const cls =
                c.category === sel.hottest ? "hot" : c.category === sel.coldest ? "cold" : "";
              return (
                <div key={c.category} className={`ibar-row ${cls}`}>
                  <span className="ibar-cat">{c.category}</span>
                  <span className="ibar-track">
                    <span className="ibar-zero" style={{ left: "50%" }} />
                    <span
                      className="ibar-fill"
                      style={{
                        left: positive ? "50%" : `${50 - half}%`,
                        width: `${half}%`,
                        background: positive ? HOT : COLD,
                      }}
                    />
                  </span>
                  <span className="ibar-val">{pp(c.yoy)}</span>
                </div>
              );
            })}
          </div>
          <div className="footnote" style={{ marginTop: 8 }}>
            Bars are each group's 12-month inflation, diverging from zero (warm = above,
            cool = below). The wider the fan, the more <em>localized</em> the inflation.
          </div>
        </div>
      )}

      <details className="methodology panel">
        <summary>Methodology &amp; sources</summary>
        <div className="method-body">
          <p>
            <strong>Idea.</strong> A supply shock to one sector shifts <em>relative</em>{" "}
            prices. Reallocation frictions (specific skills, sunk capital, switching
            costs) keep resources — and the incomes paid to them — stuck in the
            now-lower-value activity, so the shock shows up as a widening <em>spread</em>{" "}
            of inflation across sectors rather than a uniform rise. Ball &amp; Mankiw
            (1995), “Relative-Price Changes as Aggregate Supply Shocks,” formalise why
            this cross-sectional dispersion and skew co-move with headline inflation.
          </p>
          <p>
            <strong>Data.</strong> {data.source} We track the six CPI major groups with
            continuous monthly history since 1967 ({data.categories.join(", ")}), so the
            dispersion series is comparable across the 1974, 1980, 2008 and 2021–22
            episodes. Recreation and Education &amp; communication (added in the 1998 CPI
            revision) are omitted to keep the panel consistent. Series are CPI-U, U.S.
            city average, not seasonally adjusted; we use 12-month changes.
          </p>
          <p>
            <strong>Measures.</strong> {data.definition}
          </p>
          <p>
            <strong>Caveats.</strong> A relative-price shock is not, by itself, aggregate
            inflation — it becomes generalized only with maintained nominal demand and
            monetary accommodation. Dispersion across six broad groups is unweighted;
            expenditure-weighted dispersion is a planned refinement. This is one lens on
            “negative productivity,” not the whole story (see ticket 0010).
          </p>
        </div>
      </details>
    </div>
  );
}

function nearestIdx(series, t) {
  let best = 0;
  for (let i = 1; i < series.length; i++) {
    if (Math.abs(series[i].t - t) < Math.abs(series[best].t - t)) best = i;
  }
  return best;
}
