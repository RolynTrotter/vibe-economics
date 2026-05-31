// Subnational GDP comparison (ticket 0002).
// Places US states and whole countries on ONE ranked ladder on a chosen basis —
// total nominal GDP, total PPP GDP, or GDP-per-capita PPP — so you can see "this
// state ≈ that country". Switching the basis FLIP-animates each place to its new
// rank, so you watch the ladder reshuffle instead of jumping. US states are a
// light-blue bloc (coloured by their nation); countries are coloured by region,
// so the blue states visibly slide around among the world's economies.
//
// Deployed app is static: this computes client-side from public/data/subnational_gdp.json
// using subnationalGdpModel.js (a 1:1 port of the tested Python model).
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { loadDataset } from "../data.js";
import * as m from "./subnationalGdpModel.js";

const BASES = [
  { key: "nominal", label: "Total GDP" },
  { key: "ppp", label: "GDP (PPP)" },
  { key: "per_capita", label: "Per capita" },
  { key: "median_income", label: "Median income" },
];

const KINDS = [
  { key: "all", label: "States + countries", kinds: null },
  { key: "state", label: "States only", kinds: ["state"] },
  { key: "country", label: "Countries only", kinds: ["country"] },
];

// Region -> colour. US bloc (states) is a "nice light blue"; other countries are
// coloured by World Bank region so the chart is legible and the blue cluster pops.
const USA_BLUE = "#6db3f2";
function regionColor(region) {
  const r = (region || "").trim();
  if (r === "United States") return USA_BLUE;
  if (r.startsWith("East Asia")) return "#f6c453";
  if (r.startsWith("Europe")) return "#8e7dff";
  if (r.startsWith("Latin America")) return "#5ddc9a";
  if (r.startsWith("Middle East")) return "#ff9f6b";
  if (r.startsWith("North America")) return "#4fd1c5";
  if (r.startsWith("South Asia")) return "#f78fb3";
  if (r.startsWith("Sub-Saharan")) return "#c7d96b";
  return "#9fb0d8";
}

const LEGEND = [
  ["US states", USA_BLUE],
  ["Europe & Central Asia", "#8e7dff"],
  ["East Asia & Pacific", "#f6c453"],
  ["South Asia", "#f78fb3"],
  ["Latin America", "#5ddc9a"],
  ["Middle East & N. Africa", "#ff9f6b"],
  ["Sub-Saharan Africa", "#c7d96b"],
  ["North America (other)", "#4fd1c5"],
];

function fmtUSD(v) {
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(0)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${Math.round(v).toLocaleString()}`;
}
const fmtPerCapita = (v) => `$${Math.round(v).toLocaleString()}`;

const DEFAULT_LIMIT = 40;

export default function SubnationalGdp() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [basis, setBasis] = useState("nominal");
  const [kindKey, setKindKey] = useState("all");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [matchState, setMatchState] = useState("US-CA");
  const [removeCapital, setRemoveCapital] = useState(false);
  const [removeLargest, setRemoveLargest] = useState(false);
  const [removeRichest, setRemoveRichest] = useState(false);
  const [excludeCities, setExcludeCities] = useState(false);
  const [year, setYear] = useState(null);

  useEffect(() => {
    loadDataset("subnational_gdp")
      .then((d) => {
        setData(d);
        setYear(d.years?.default ?? null);
      })
      .catch((e) => setError(e.message));
  }, []);

  // The year the table is aligned to (slider value, falling back to the dataset default).
  const yearMeta = data?.years ?? null;
  const effYear = year ?? yearMeta?.default ?? null;
  // Per-year entity table (smoothed/imputed in Python, exported per year), or the
  // latest snapshot for older static files without `by_year`.
  const yearEntities = useMemo(() => {
    if (!data) return [];
    if (data.by_year && effYear != null && data.by_year[String(effYear)]) {
      return data.by_year[String(effYear)];
    }
    return data.entities || [];
  }, [data, effYear]);

  const kinds = KINDS.find((k) => k.key === kindKey)?.kinds ?? null;
  const isMedian = basis === "median_income";
  // Median basis: "exclude cities" switches to the directly-measured rural median.
  const effectiveBasis = isMedian && excludeCities ? "median_income_rural" : basis;
  const isPerCapita = basis === "per_capita";
  const smallVal = isPerCapita || isMedian; // plain-$ formatting (median + rural)
  // Metro punch-out is GDP-only: there's no metro-level median income to subtract.
  const punchoutAllowed = !isMedian;
  const punchout = punchoutAllowed && (removeCapital || removeLargest || removeRichest);
  const hinterland = punchout && data?.hinterland?.places?.length;

  const table = useMemo(() => {
    if (!data) return [];
    if (punchout) {
      if (!data.hinterland?.places?.length) return [];
      return m.hinterlandTable(data.hinterland.places, basis, removeCapital, removeLargest, removeRichest, kinds);
    }
    return m.rankedTable(yearEntities, effectiveBasis, kinds);
  }, [data, yearEntities, effectiveBasis, kindKey, removeCapital, removeLargest, removeRichest, punchout, basis]);
  const nEstimated = useMemo(() => (punchout ? 0 : table.filter((e) => e.estimated).length), [table, punchout]);

  const q = query.trim().toLowerCase();
  const filtered = useMemo(
    () => (q ? table.filter((e) => e.name.toLowerCase().includes(q)) : table),
    [table, q]
  );
  const limit = expanded || q ? filtered.length : DEFAULT_LIMIT;
  const visible = filtered.slice(0, limit);
  const maxValue = table.length ? table[0].value : 1; // global max for bar scaling

  const states = useMemo(
    () => (data ? (data.entities || []).filter((e) => e.kind === "state").sort((a, b) => a.name.localeCompare(b.name)) : []),
    [data]
  );
  const match = useMemo(
    () => (data ? m.nearest(yearEntities, matchState, effectiveBasis, 3, "country") : null),
    [data, yearEntities, matchState, effectiveBasis]
  );

  // ---- FLIP: animate rows from their previous position to the new one. ----
  const rowRefs = useRef(new Map());
  const prevPos = useRef(new Map());
  useLayoutEffect(() => {
    const newPos = new Map();
    rowRefs.current.forEach((el, id) => {
      if (el) newPos.set(id, el.getBoundingClientRect().top);
    });
    newPos.forEach((top, id) => {
      const prev = prevPos.current.get(id);
      const el = rowRefs.current.get(id);
      if (prev != null && el && Math.abs(prev - top) > 1) {
        el.animate(
          [{ transform: `translateY(${prev - top}px)` }, { transform: "translateY(0)" }],
          { duration: 600, easing: "cubic-bezier(.22,.61,.36,1)" }
        );
      }
    });
    prevPos.current = newPos;
  }, [basis, kindKey, visible.length, q, removeCapital, removeLargest, effYear]);

  const basisSpec = m.BASES[effectiveBasis];
  // Value string with a trailing asterisk when the figure was interpolated/extrapolated.
  const fmtVal = (e) => {
    const s = smallVal ? fmtPerCapita(e.value) : fmtUSD(e.value);
    return e.estimated ? `${s}*` : s;
  };

  return (
    <div>
      <div className="panel controls">
        {yearMeta && (
          <div>
            <div className="footnote" style={{ marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
              <span>Align all places to year</span>
              <strong style={{ fontVariantNumeric: "tabular-nums" }}>{effYear}</strong>
            </div>
            <input
              type="range"
              min={yearMeta.min}
              max={yearMeta.max}
              step={1}
              value={effYear ?? yearMeta.max}
              disabled={punchout}
              onChange={(e) => setYear(Number(e.target.value))}
              style={{ width: "100%" }}
              aria-label="Year"
            />
            <div className="footnote" style={{ marginTop: 4 }}>
              {punchout
                ? "Metro punch-out uses the latest-vintage data; the year slider doesn’t apply here."
                : `Sources lag differently, so figures past a source’s latest release are interpolated or carried forward (IMF growth) and marked *. ${nEstimated} of ${table.length} shown are estimated.`}
            </div>
          </div>
        )}
        <div>
          <div className="footnote" style={{ marginBottom: 6 }}>Rank by</div>
          <div className="seg">
            {BASES.map((b) => (
              <button key={b.key} className={basis === b.key ? "active" : ""} onClick={() => setBasis(b.key)}>
                {b.label}
              </button>
            ))}
          </div>
          <div className="footnote" style={{ marginTop: 8 }}>{basisSpec?.blurb}</div>
        </div>

        <div className="seg">
          {KINDS.map((k) => (
            <button key={k.key} className={kindKey === k.key ? "active" : ""} onClick={() => setKindKey(k.key)}>
              {k.label}
            </button>
          ))}
        </div>

        {punchoutAllowed ? (
        <div>
          <div className="footnote" style={{ marginBottom: 6 }}>
            Punch out global cities <span style={{ opacity: 0.7 }}>· OECD countries only</span>
          </div>
          <div className="seg">
            <button className={removeCapital ? "active" : ""} onClick={() => setRemoveCapital((v) => !v)}>
              {removeCapital ? "✓ " : ""}Capital
            </button>
            <button className={removeLargest ? "active" : ""} onClick={() => setRemoveLargest((v) => !v)}>
              {removeLargest ? "✓ " : ""}Largest
            </button>
            <button className={removeRichest ? "active" : ""} onClick={() => setRemoveRichest((v) => !v)}>
              {removeRichest ? "✓ " : ""}Richest
            </button>
          </div>
          {hinterland && (
            <div className="footnote" style={{ marginTop: 8 }}>
              Hinterland view: each economy minus its selected metro(s)
              {" "}({[removeCapital && "capital", removeLargest && "largest",
                    removeRichest && "richest (GDP/capita)"].filter(Boolean).join(", ")}),
              recomputed on what’s left. US states (CSA footprint, by county) sit
              alongside OECD countries (FUA) and big non-OECD economies (China, India,
              Brazil… marked <em>est.</em> — curated metro estimates). Places that are
              essentially all-metro (e.g. New Jersey) are hidden.
            </div>
          )}
        </div>
        ) : (
          <div>
            <div className="footnote" style={{ marginBottom: 6 }}>
              Exclude big cities <span style={{ opacity: 0.7 }}>· rural median, EU + US</span>
            </div>
            <div className="seg">
              <button className={excludeCities ? "active" : ""} onClick={() => setExcludeCities((v) => !v)}>
                {excludeCities ? "✓ " : ""}Outside the cities
              </button>
            </div>
            <div className="footnote" style={{ marginTop: 8 }}>
              {excludeCities
                ? "Median income outside the big cities — Europe: Eurostat rural areas; US states: nonmetro counties. Directly measured (medians can’t be subtracted). Places without a rural figure drop out."
                : "What a typical household lives on. Toggle to compare the median outside the big cities."}
            </div>
          </div>
        )}

        <input
          className="search"
          type="search"
          placeholder={hinterland ? "Find a country…" : "Find a state or country…"}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {error && <div className="panel error">Error: {error}</div>}
      {!data && !error && <div className="panel loading">Loading data…</div>}

      {data && (
        <>
          {/* "Your state ≈ country" matcher (whole-economy view only) */}
          {!hinterland && (
          <div className="panel">
            <div className="chart-title">Your state ≈ which country?</div>
            <select className="search" value={matchState} onChange={(e) => setMatchState(e.target.value)}>
              {states.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            {!match && (
              <div className="footnote" style={{ marginTop: 10 }}>
                {matchState} isn’t ranked on this basis. DC is excluded from the
                per-capita view (its GDP/capita is a commuter artifact).
              </div>
            )}
            {match && (
              <div className="match-row">
                <div className="match-target" style={{ borderColor: USA_BLUE }}>
                  <div className="label">{match.entity.name}</div>
                  <div className="value">{fmtVal(match.entity)}</div>
                  <div className="sub">#{match.entity.rank} overall · {effYear}</div>
                </div>
                <div className="match-approx">≈</div>
                <div className="match-countries">
                  {match.nearest.map((n) => (
                    <div key={n.id} className="match-country">
                      <span className="swatch" style={{ background: regionColor(n.region) }} />
                      <span className="cname">{n.name}</span>
                      <span className="cval">{fmtVal(n)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          )}

          {/* The animated ladder */}
          <div className="panel">
            <div className="chart-title">
              {basisSpec?.label}
              {hinterland ? " — hinterlands (metros removed)" : " — world ranking"} (
              {filtered.length}
              {q ? " matches" : hinterland ? " countries" : " places"})
            </div>
            <div className="ladder">
              {visible.map((e) => {
                const color = regionColor(e.region);
                const w = Math.max(2, (Math.sqrt(e.value) / Math.sqrt(maxValue)) * 100);
                const hit = q && e.name.toLowerCase().includes(q);
                return (
                  <div
                    key={e.id}
                    ref={(el) => {
                      if (el) rowRefs.current.set(e.id, el);
                      else rowRefs.current.delete(e.id);
                    }}
                    className={`lrow${e.kind === "state" ? " is-state" : ""}${e.id === "USA" ? " is-state" : ""}${hit ? " hit" : ""}`}
                  >
                    <span className="lrank">{e.rank}</span>
                    <span className={`lname${e.removed?.length ? " lname-scroll" : ""}`}>
                      {e.name}
                      {e.curated ? <span className="lest" title="curated metro estimate">est.</span> : null}
                      {isMedian && e.median_income_year && e.median_income_year < 2023 ? (
                        <sup
                          className={`lmi-yr${e.median_income_year < 2022 ? " stale" : " lagged"}`}
                          title={`Income data from ${e.median_income_year} OECD IDD (most countries: 2023)`}
                        >{e.median_income_year}</sup>
                      ) : null}
                      {e.removed?.length ? (
                        <span className="lremoved"> − {e.removed.join(", ")}</span>
                      ) : null}
                    </span>
                    <span className="lbar-wrap">
                      <span className="lbar" style={{ width: `${w}%`, background: color }} />
                    </span>
                    <span className={`lval${e.estimated ? " lval-est" : ""}`}
                          title={e.estimated ? `Estimated for ${effYear} (interpolated or carried forward)` : undefined}>
                      {fmtVal(e)}
                    </span>
                  </div>
                );
              })}
            </div>
            {!q && filtered.length > DEFAULT_LIMIT && (
              <button className="link-btn" onClick={() => setExpanded((x) => !x)}>
                {expanded ? "Show top 40" : `Show all ${filtered.length}`}
              </button>
            )}
            <div className="legend">
              {LEGEND.map(([label, c]) => (
                <span key={label} className="legend-item">
                  <span className="swatch" style={{ background: c }} />
                  {label}
                </span>
              ))}
            </div>
            <div className="footnote" style={{ marginTop: 6 }}>
              Bars are √-scaled for legibility; the figure on the right is the value.
              {!hinterland && (
                <>
                  {" "}An asterisk (*) marks a figure <strong>estimated for {effYear}</strong>:
                  either interpolated between two releases, or the latest actual carried
                  forward (≤2 yrs) using IMF growth. A place with no data within ~2 years of
                  {" "}{effYear} drops out rather than being invented.
                  {nEstimated > 0 ? ` Here, ${nEstimated} of ${table.length} are estimated.` : ""}
                </>
              )}
              {hinterland ? ` ${data.hinterland.note}` : ""}
            </div>
          </div>

          <div className="panel footnote">
            <details className="methodology">
              <summary>Data sources &amp; methodology</summary>
              <div className="method-body">
                <p><strong>Same-year alignment (the year slider)</strong><br />
                Sources release on different clocks — BEA publishes a preliminary US-state
                figure for the current year while the World Bank’s country GDP often stops
                one or two years back. The slider pins every place to one chosen year and
                fills the gaps per metric (nominal GDP, PPP GDP, population) independently:
                an observed value is used as-is; a year between two observations is
                interpolated log-linearly (constant growth); a year up to two years past
                the last observation is carried forward by IMF WEO year-on-year growth
                (or the place’s own recent CAGR if the IMF lacks it). Anything filled this
                way is marked <strong>*</strong>. A place whose data ends more than ~2 years
                before the chosen year is dropped for that year rather than invented — so a
                country with nothing since 2021 won’t appear at 2025, but one with 2025
                nominal GDP, 2024 population and a 2023 median can still be assembled.
                Median income is carried from its own vintage to the chosen year by
                PPP-per-capita growth.</p>

                <p><strong>Total GDP (nominal / PPP)</strong><br />
                Countries: World Bank WDI 2024 — nominal at market exchange rates; PPP via
                World Bank conversion factors. US states: BEA Regional 2025 (preliminary) —
                nominal only; PPP proxy = nominal (US ≈ PPP reference economy, ratio ≈ 1.01).
                States are one year ahead of countries; for fast-growing economies this gap
                is real.</p>

                <p><strong>GDP per capita (PPP)</strong><br />
                PPP GDP ÷ population (World Bank / BEA-derived).
                DC is excluded: its output is attributed to metro-wide workers but divided
                by DC residents alone, producing an artifact ~3× the true level.</p>

                <p><strong>Median income (PPP)</strong><br />
                Countries: OECD Income Distribution Database — median equivalised disposable
                income (national currency) ÷ World Bank private-consumption PPP. Income data
                vintage varies by country: most 2022–2023; Russia &amp; South Africa 2017;
                Japan 2021; Australia 2020. Stale figures are tagged with their year in the
                ladder. US states: Census ACS 2023 (5-year) median household income × a US
                anchor ratio (OECD US equivalised median ÷ Census US median) to put states
                on the OECD equivalised scale. Comparable in level but not size-adjusted
                across countries; OECD/EU coverage only.</p>

                <p><strong>Hinterland (metro punch-out)</strong><br />
                OECD countries: Functional Urban Area (FUA) metro GDP shares, vintage
                2021–2023 (typically 2–3 years behind the national GDP they are applied to).
                US states: BEA county GDP (place of work) + Census county population
                (residence) over each metro's CSA footprint, 2023. Non-OECD economies
                (China, India, Brazil, Russia, etc.): curated estimates from public reporting,
                marked <em>est.</em> — ballpark, not gospel. National GDP totals are the same
                2024/2025 WDI/BEA figures as the main ranking; only the metro <em>shares</em>
                carry the older vintage.</p>

                <p style={{ marginBottom: 0 }}><strong>Sources:</strong> {data.sources}</p>
              </div>
            </details>
            {data.caveats.length > 0 && (
              <ul style={{ margin: "10px 0 0", paddingLeft: 18 }}>
                {data.caveats.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
