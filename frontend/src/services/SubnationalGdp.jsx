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

  useEffect(() => {
    loadDataset("subnational_gdp").then(setData).catch((e) => setError(e.message));
  }, []);

  const kinds = KINDS.find((k) => k.key === kindKey)?.kinds ?? null;
  const isPerCapita = basis === "per_capita";
  const hinterland = (removeCapital || removeLargest) && data?.hinterland?.places?.length;

  const table = useMemo(() => {
    if (!data) return [];
    if (removeCapital || removeLargest) {
      if (!data.hinterland?.places?.length) return [];
      return m.hinterlandTable(data.hinterland.places, basis, removeCapital, removeLargest, kinds);
    }
    return m.rankedTable(data.entities, basis, kinds);
  }, [data, basis, kindKey, removeCapital, removeLargest]);

  const q = query.trim().toLowerCase();
  const filtered = useMemo(
    () => (q ? table.filter((e) => e.name.toLowerCase().includes(q)) : table),
    [table, q]
  );
  const limit = expanded || q ? filtered.length : DEFAULT_LIMIT;
  const visible = filtered.slice(0, limit);
  const maxValue = table.length ? table[0].value : 1; // global max for bar scaling

  const states = useMemo(
    () => (data ? data.entities.filter((e) => e.kind === "state").sort((a, b) => a.name.localeCompare(b.name)) : []),
    [data]
  );
  const match = useMemo(
    () => (data ? m.nearest(data.entities, matchState, basis, 3, "country") : null),
    [data, matchState, basis]
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
  }, [basis, kindKey, visible.length, q, removeCapital, removeLargest]);

  const basisSpec = m.BASES[basis];

  return (
    <div>
      <div className="panel controls">
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

        <div>
          <div className="footnote" style={{ marginBottom: 6 }}>
            Punch out global cities <span style={{ opacity: 0.7 }}>· OECD countries only</span>
          </div>
          <div className="seg">
            <button className={removeCapital ? "active" : ""} onClick={() => setRemoveCapital((v) => !v)}>
              {removeCapital ? "✓ " : ""}Capital metro
            </button>
            <button className={removeLargest ? "active" : ""} onClick={() => setRemoveLargest((v) => !v)}>
              {removeLargest ? "✓ " : ""}Largest metro
            </button>
          </div>
          {hinterland && (
            <div className="footnote" style={{ marginTop: 8 }}>
              Hinterland view: each economy minus its{" "}
              {removeCapital && removeLargest ? "capital and largest" : removeCapital ? "capital" : "largest"}{" "}
              metro, recomputed on what’s left. US states (CSA footprint, by county) sit
              alongside OECD countries (FUA). Non-OECD countries and places that are
              essentially all-metro (e.g. New Jersey) are hidden.
            </div>
          )}
        </div>

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
                  <div className="value">
                    {isPerCapita ? fmtPerCapita(match.entity.value) : fmtUSD(match.entity.value)}
                  </div>
                  <div className="sub">#{match.entity.rank} overall · {match.entity.year}</div>
                </div>
                <div className="match-approx">≈</div>
                <div className="match-countries">
                  {match.nearest.map((n) => (
                    <div key={n.id} className="match-country">
                      <span className="swatch" style={{ background: regionColor(n.region) }} />
                      <span className="cname">{n.name}</span>
                      <span className="cval">{isPerCapita ? fmtPerCapita(n.value) : fmtUSD(n.value)}</span>
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
                    <span className="lname">
                      {e.name}
                      {e.removed?.length ? (
                        <span className="lremoved"> − {e.removed.join(", ")}</span>
                      ) : null}
                    </span>
                    <span className="lbar-wrap">
                      <span className="lbar" style={{ width: `${w}%`, background: color }} />
                    </span>
                    <span className="lval">{isPerCapita ? fmtPerCapita(e.value) : fmtUSD(e.value)}</span>
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
              Bars are √-scaled for legibility; the figure on the right is the actual value.
              {hinterland ? ` ${data.hinterland.note}` : ""}
            </div>
          </div>

          <div className="panel footnote">
            {data.sources}
            <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
              {data.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
