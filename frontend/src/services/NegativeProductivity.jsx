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
  { key: "zombies", label: "Zombie firms", ready: true },
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
      {lens === "zombies" && <ZombieLens />}
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

// ---- Lens 2: zombie firms (interest coverage < 1 for ≥3 years) ----------------
const usd = (v) =>
  Math.abs(v) >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${Math.round(v / 1e6)}M`;

function ZombieLens() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [matureOnly, setMatureOnly] = useState(true);

  useEffect(() => {
    loadDataset("negative_productivity_zombies").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="panel error">Error: {error}</div>;
  if (!data) return <div className="panel loading">Loading SEC fundamentals…</div>;

  // Lines use only complete years so the provisional latest dip doesn't mislead.
  const complete = data.series.filter((r) => !r.provisional && r.mature_share != null);
  const latestComplete = complete[complete.length - 1];
  const broadLatest = data.series.filter((r) => !r.provisional).slice(-1)[0];

  const charts = [
    {
      label: "All firms (ICR<1, 3 yrs)",
      color: "#9fb0d8",
      points: data.series.filter((r) => !r.provisional).map((r) => ({ x: r.year, y: r.share })),
    },
    {
      label: "Mature firms (≥10y reporting)",
      color: HOT,
      points: complete.map((r) => ({ x: r.year, y: r.mature_share })),
    },
  ];

  const roster = matureOnly ? data.latest_mature : data.latest_all;
  const maxInt = Math.max(1, ...roster.firms.map((f) => f.interest));

  return (
    <div>
      <div className="panel">
        <div className="cards">
          <MetricCard
            label={`Mature zombies · ${latestComplete?.year ?? "—"}`}
            value={latestComplete ? `${latestComplete.mature_share.toFixed(1)}%` : "—"}
            sub={`${latestComplete?.n_mature_zombies ?? 0} of ${latestComplete?.n_mature ?? 0} firms ≥10y old`}
            tone={latestComplete && latestComplete.mature_share >= 20 ? "bad" : "warn"}
          />
          <MetricCard
            label="All listed firms"
            value={broadLatest ? `${broadLatest.share.toFixed(1)}%` : "—"}
            sub={`${broadLatest?.n_zombies ?? 0} of ${broadLatest?.n_firms ?? 0} with 3-yr data`}
            tone="warn"
          />
          <MetricCard
            label="Peak mature share"
            value={`${Math.max(...complete.map((r) => r.mature_share)).toFixed(1)}%`}
            sub={`yr ${complete.reduce((a, b) => (b.mature_share > a.mature_share ? b : a)).year} — cheap-money era`}
          />
          <MetricCard
            label="Debt they can't service"
            value={usd(roster.firms.reduce((s, f) => s + f.interest, 0))}
            sub={`interest owed by the top ${roster.firms.length} ${matureOnly ? "mature " : ""}zombies`}
            tone="bad"
          />
        </div>
      </div>

      <div className="panel">
        <div className="chart-title">
          Share of US-listed firms that are zombies, {complete[0]?.year}–{latestComplete?.year}
        </div>
        <LineChart
          series={charts}
          yFormat={(v) => `${v.toFixed(0)}%`}
          xLabel="year"
          yLabel="% of firms"
          height={230}
        />
        <div className="footnote" style={{ marginTop: 8 }}>
          A zombie can't cover its interest from operating earnings (interest-coverage
          ratio &lt; 1) for three years running — alive only by rolling over debt, tying
          up capital and labour that healthier firms could use. The mature-firm line
          climbs through the cheap-money 2010s, peaks around 2021–22, and eases as rates
          rise. Levels run high because financials and small loss-makers aren't excluded —
          read the trend. The latest year(s) are omitted while filings arrive.
        </div>
      </div>

      <div className="panel">
        <div className="chart-title">
          Biggest zombies by unpayable interest — {roster.year}
        </div>
        <div className="seg" style={{ marginBottom: 10 }}>
          {[
            [true, "Mature (≥10y)"],
            [false, "All firms"],
          ].map(([v, lab]) => (
            <button key={String(v)} className={matureOnly === v ? "active" : ""} onClick={() => setMatureOnly(v)}>
              {lab}
            </button>
          ))}
        </div>
        <div className="ibars">
          {roster.firms.map((f) => (
            <div key={f.name + f.since} className="ibar-row">
              <span className="ibar-cat" style={{ flexBasis: "46%" }} title={f.name}>
                {f.name}
                <span className="footnote" style={{ marginLeft: 6 }}>{f.loc}</span>
              </span>
              <span className="ibar-track">
                <span
                  className="ibar-fill"
                  style={{ left: 0, width: `${(f.interest / maxInt) * 100}%`, background: HOT }}
                />
              </span>
              <span className="ibar-val" style={{ width: 96 }}>
                {usd(f.interest)} · {f.icr < 0 ? "ICR<0" : `ICR ${f.icr.toFixed(2)}`}
              </span>
            </div>
          ))}
        </div>
        <div className="footnote" style={{ marginTop: 8 }}>
          Ranked by interest expense — the size of the debt service these firms' earnings
          didn't cover. ICR &lt; 0 means operating losses (negative EBIT). Familiar names
          here are the ones a long stretch of cheap credit kept upright.
        </div>
      </div>

      <details className="methodology panel">
        <summary>Methodology &amp; sources</summary>
        <div className="method-body">
          <p>
            <strong>Definition.</strong> {data.definition} (BIS — Banerjee &amp; Hofmann,
            2018/2020.) The ≥3-year / age screen is deliberate: a young firm investing
            through early losses is <em>not</em> a zombie.
          </p>
          <p>
            <strong>Data.</strong> {data.source} Interest-coverage = EBIT
            (OperatingIncomeLoss) ÷ InterestExpense, computed where interest &gt; 0.
          </p>
          <p><strong>Caveats.</strong></p>
          <ul className="footnote" style={{ margin: 0, paddingLeft: 18 }}>
            {data.caveats.map((c, i) => (
              <li key={i} style={{ marginBottom: 4 }}>{c}</li>
            ))}
          </ul>
        </div>
      </details>
    </div>
  );
}
