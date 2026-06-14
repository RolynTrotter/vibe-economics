// ESPP Analyzer — APY *and* raw total return on the average invested dollar of an
// ESPP, vs the S&P 500, at the 25th / median / 75th percentile of single-stock
// outcomes. You set the four knobs of a real plan: contribution term, holding
// period after purchase, lookback, and discount.
//
// Deployed app is static, so this reads a committed snapshot
// (public/data/espp_analyzer.json) that precomputes every (term, hold, lookback,
// discount) cell with the tested Python model — the widget just looks up its cell.
import { useEffect, useMemo, useState } from "react";
import { loadDataset } from "../data.js";

const pct = (v) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);
const pct0 = (v) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`);
const tone = (v) => (v == null ? undefined : v >= 0.05 ? "good" : v <= 0 ? "bad" : "warn");

// One labelled row of three percentile cards (25th / median / 75th).
function PctRow({ label, vals, colored }) {
  const cells = [
    ["p25", "25th", false],
    ["median", "median", true],
    ["p75", "75th", false],
  ];
  return (
    <div>
      <div className="pctrow-label">{label}</div>
      <div className="cards cards-3">
        {cells.map(([k, head, mid]) => {
          const t = colored ? tone(vals[k]) : undefined;
          return (
            <div key={k} className={`card${t ? " " + t : ""}${mid ? " is-median" : ""}`}>
              <div className="label">{head}</div>
              <div className="value">{pct(vals[k])}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function EsppAnalyzer() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [term, setTerm] = useState(6);
  const [hold, setHold] = useState(12);
  const [lookback, setLookback] = useState(true);
  const [discount, setDiscount] = useState(15); // integer %

  useEffect(() => {
    loadDataset("espp_analyzer")
      .then((d) => {
        setData(d);
        setTerm(d.defaults.term);
        setHold(d.defaults.hold);
        setLookback(d.defaults.lookback);
        setDiscount(d.defaults.discount);
      })
      .catch((e) => setError(e.message));
  }, []);

  const cell = useMemo(() => {
    if (!data) return null;
    const key = `${term}|${hold}|${lookback ? 1 : 0}|${discount}`;
    return data.grid[key] ?? null;
  }, [data, term, hold, lookback, discount]);

  const Seg = ({ value, set, options, fmt }) => (
    <div className="seg">
      {options.map((o) => (
        <button key={o} className={value === o ? "active" : ""} onClick={() => set(o)}>
          {fmt(o)}
        </button>
      ))}
    </div>
  );

  const sp = <>S&amp;P 500 <span className="pl-sub">· same window</span></>;
  const yrs = cell ? cell.years.toFixed(2) : "—";

  return (
    <div>
      <div className="panel">
        <div className="footnote" style={{ marginBottom: 10 }}>
          What does an ESPP actually pay on the <b>average dollar</b> you put in —
          and how does that compare to just buying the index? Dollars sit idle as cash
          until the purchase date, then ride a single stock. Set your plan's terms; the
          ranges below are the 25th–75th percentile across S&P 500 stocks.
        </div>

        <label className="field" style={{ gap: 6 }}>
          Contribution term (offering period)
          <Seg value={term} set={setTerm} options={data?.term_options ?? [3, 6, 12]}
            fmt={(o) => `${o} mo`} />
        </label>

        <label className="field" style={{ gap: 6, marginTop: 12 }}>
          Holding period after purchase
          <Seg value={hold} set={setHold} options={data?.hold_options ?? [0, 6, 12, 18, 24]}
            fmt={(o) => (o === 0 ? "sell now" : `${o} mo`)} />
        </label>

        <label className="field" style={{ gap: 6, marginTop: 12 }}>
          Lookback (price = lower of start vs purchase date)
          <div className="seg">
            <button className={lookback ? "active" : ""} onClick={() => setLookback(true)}>
              Lookback
            </button>
            <button className={!lookback ? "active" : ""} onClick={() => setLookback(false)}>
              No lookback
            </button>
          </div>
        </label>

        <label className="field" style={{ marginTop: 12 }}>
          Purchase discount <span className="val">{discount}%</span>
          <input type="range" min="0" max={data?.discount_max ?? 30} step="1"
            value={discount} onChange={(e) => setDiscount(parseInt(e.target.value, 10))} />
        </label>
      </div>

      {error && <div className="panel error">Error: {error}</div>}
      {!data && !error && <div className="panel loading">Loading data…</div>}

      {cell && (
        <>
          <div className="panel">
            <div className="chart-title">Annualised return (APY) — average invested dollar</div>
            <div className="footnote" style={{ margin: "4px 0 2px" }}>
              Capital committed ≈ <b>{yrs} yr</b> (term/2 + hold). ESPP beats the index
              in <b>{pct0(cell.beat)}</b> of cases; the average dollar ends at a loss{" "}
              <b>{pct0(cell.loss)}</b> of the time.
            </div>
            <PctRow label="Spread (ESPP − S&P)" vals={cell.spread} colored />
            <PctRow label="ESPP on your cash" vals={cell.espp} />
            <PctRow label={sp} vals={cell.index} />
          </div>

          <div className="panel">
            <div className="chart-title">Total return over the {yrs}-yr commit (raw, not annualised)</div>
            <PctRow label="Spread (ESPP − S&P)" vals={cell.spread_raw} colored />
            <PctRow label="ESPP on your cash" vals={cell.espp_raw} />
            <PctRow label={sp} vals={cell.index_raw} />
            <div className="footnote" style={{ marginTop: 10 }}>
              The {discount}% discount is a one-time head start of {pct(cell.head_start)} on
              your cash. {lookback
                ? "The lookback also lets you buy at the lower of the start and purchase prices — usually a bigger lever than the discount itself."
                : "With no lookback you only get the flat discount off the purchase-date price."}{" "}
              {hold === 0
                ? "Selling at purchase makes the raw return modest but the APY huge — a one-off edge stretched to a yearly rate."
                : `Holding ${hold} months exposes you to one stock's swings, which is what widens the 25th–75th range.`}
            </div>
          </div>

          <div className="panel footnote">
            <b>Source:</b> {data.source} {data.n_tickers} current members,{" "}
            {data.first_year}–{data.last_year}. {data.definition}
            <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
              {data.caveats.map((c, i) => (
                <li key={i} style={{ marginBottom: 4 }}>{c}</li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
