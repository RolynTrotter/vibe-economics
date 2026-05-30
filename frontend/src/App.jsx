// Simple mobile-first shell with a horizontal service nav. Add a service by
// importing its screen and adding an entry to SERVICES (planned ones are
// disabled until their backend lands).
import { useState } from "react";
import SafeWithdrawal from "./services/SafeWithdrawal.jsx";
import SubnationalGdp from "./services/SubnationalGdp.jsx";

const SERVICES = [
  { key: "safe_withdrawal", label: "Safe Withdrawal", Component: SafeWithdrawal },
  { key: "subnational_gdp", label: "Subnational GDP", Component: SubnationalGdp },
  { key: "cost_of_living", label: "Cost of Living", Component: null },
  { key: "currency", label: "Currency", Component: null },
  { key: "fed_wealth", label: "Fed Wealth/Income", Component: null },
];

export default function App() {
  const [active, setActive] = useState("safe_withdrawal");
  const current = SERVICES.find((s) => s.key === active);
  const Component = current?.Component;

  return (
    <div className="app">
      <header className="app-header">
        <h1>vibe-economics</h1>
        <p>Small economics utilities — explore and verify on your phone.</p>
      </header>

      <nav className="nav">
        {SERVICES.map((s) => (
          <button
            key={s.key}
            className={active === s.key ? "active" : ""}
            disabled={!s.Component}
            onClick={() => s.Component && setActive(s.key)}
            title={s.Component ? "" : "Planned — see docs/tickets"}
          >
            {s.label}
            {!s.Component ? " ·soon" : ""}
          </button>
        ))}
      </nav>

      {Component ? <Component /> : <div className="panel">Coming soon.</div>}
    </div>
  );
}
