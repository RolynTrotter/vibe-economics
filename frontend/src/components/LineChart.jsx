// Minimal dependency-free responsive SVG line chart, tuned to be legible on a
// phone. Supports multiple series and horizontal reference lines (e.g. the 4%
// rule baseline). Reused across services.
//
// Props:
//   series:   [{ label, color, points: [{x, y}] }]
//   refLines: [{ y, label, color }]   (optional)
//   height:   number (px, default 220)
//   yFormat:  (v) => string           (axis + tooltip formatting)
//   xLabel, yLabel: string
import { useMemo, useState } from "react";

const PAD = { top: 12, right: 12, bottom: 28, left: 44 };

export default function LineChart({
  series = [],
  refLines = [],
  height = 220,
  yFormat = (v) => v.toFixed(2),
  xLabel,
  yLabel,
}) {
  const [hover, setHover] = useState(null);
  const width = 600; // viewBox width; SVG scales to container via CSS.

  const allPoints = series.flatMap((s) => s.points);
  const { xMin, xMax, yMin, yMax } = useMemo(() => {
    const xs = allPoints.map((p) => p.x);
    const ys = allPoints.map((p) => p.y).concat(refLines.map((r) => r.y));
    const yLo = Math.min(...ys);
    const yHi = Math.max(...ys);
    const pad = (yHi - yLo) * 0.08 || 1;
    return {
      xMin: Math.min(...xs),
      xMax: Math.max(...xs),
      yMin: yLo - pad,
      yMax: yHi + pad,
    };
  }, [allPoints, refLines]);

  if (allPoints.length === 0) return <div className="loading">No data</div>;

  const sx = (x) =>
    PAD.left + ((x - xMin) / (xMax - xMin || 1)) * (width - PAD.left - PAD.right);
  const sy = (y) =>
    PAD.top + (1 - (y - yMin) / (yMax - yMin || 1)) * (height - PAD.top - PAD.bottom);

  const yTicks = ticks(yMin, yMax, 4);
  const xTicks = ticks(xMin, xMax, 5).map(Math.round);

  function onMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * width;
    const xVal = xMin + ((px - PAD.left) / (width - PAD.left - PAD.right)) * (xMax - xMin);
    // nearest x across the first series
    const base = series[0].points;
    let best = base[0];
    for (const p of base) if (Math.abs(p.x - xVal) < Math.abs(best.x - xVal)) best = p;
    setHover(best.x);
  }

  return (
    <div className="chart-wrap">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        role="img"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        onTouchStart={(e) => onMove(e.touches[0] ? { ...e, clientX: e.touches[0].clientX, currentTarget: e.currentTarget } : e)}
      >
        {/* y grid + labels */}
        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line x1={PAD.left} x2={width - PAD.right} y1={sy(t)} y2={sy(t)} stroke="#2a3454" strokeWidth="1" />
            <text x={PAD.left - 6} y={sy(t) + 4} fontSize="11" fill="#9fb0d8" textAnchor="end">
              {yFormat(t)}
            </text>
          </g>
        ))}
        {/* x labels */}
        {xTicks.map((t) => (
          <text key={`x${t}`} x={sx(t)} y={height - 8} fontSize="11" fill="#9fb0d8" textAnchor="middle">
            {t}
          </text>
        ))}
        {/* reference lines */}
        {refLines.map((r, i) => (
          <g key={`r${i}`}>
            <line
              x1={PAD.left}
              x2={width - PAD.right}
              y1={sy(r.y)}
              y2={sy(r.y)}
              stroke={r.color || "#ffd166"}
              strokeDasharray="6 5"
              strokeWidth="1.5"
            />
            {r.label ? (
              <text x={width - PAD.right} y={sy(r.y) - 4} fontSize="11" fill={r.color || "#ffd166"} textAnchor="end">
                {r.label}
              </text>
            ) : null}
          </g>
        ))}
        {/* series */}
        {series.map((s, i) => (
          <path
            key={i}
            d={linePath(s.points, sx, sy)}
            fill="none"
            stroke={s.color}
            strokeWidth="2"
          />
        ))}
        {/* hover marker */}
        {hover != null
          ? series.map((s, i) => {
              const p = s.points.find((q) => q.x === hover);
              if (!p) return null;
              return <circle key={`h${i}`} cx={sx(p.x)} cy={sy(p.y)} r="3.5" fill={s.color} />;
            })
          : null}
      </svg>

      {/* legend + hover readout */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 12, marginTop: 6 }}>
        {series.map((s, i) => (
          <span key={i} style={{ color: s.color }}>
            ● {s.label}
            {hover != null && s.points.find((q) => q.x === hover)
              ? `: ${yFormat(s.points.find((q) => q.x === hover).y)}`
              : ""}
          </span>
        ))}
      </div>
      {(xLabel || yLabel) && (
        <div className="footnote" style={{ marginTop: 4 }}>
          {hover != null ? `${xLabel || "x"} = ${hover}` : `${xLabel || ""} · ${yLabel || ""}`}
        </div>
      )}
    </div>
  );
}

function linePath(points, sx, sy) {
  return points
    .map((p, i) => `${i === 0 ? "M" : "L"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`)
    .join(" ");
}

function ticks(lo, hi, n) {
  const step = (hi - lo) / n;
  return Array.from({ length: n + 1 }, (_, i) => lo + i * step);
}
