// Reusable headline-number card. tone: "good" | "warn" | "bad" | undefined.
export default function MetricCard({ label, value, sub, tone }) {
  return (
    <div className={`card${tone ? " " + tone : ""}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub ? <div className="sub">{sub}</div> : null}
    </div>
  );
}
