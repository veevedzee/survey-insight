import { useEffect, useState } from "react";
import { getHealth } from "./api/client";
import { StepIndicator, STEPS } from "./components/StepIndicator";

type BackendState =
  | { kind: "checking" }
  | { kind: "up"; version: string }
  | { kind: "down" };

export default function App() {
  const [backend, setBackend] = useState<BackendState>({ kind: "checking" });

  useEffect(() => {
    getHealth()
      .then((h) => setBackend({ kind: "up", version: h.version }))
      .catch(() => setBackend({ kind: "down" }));
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Survey Insight</h1>
          <p className="tagline">
            Clean survey data, sound statistics and themes from open-ended answers. Computed with
            open-source tools; your file is never stored.
          </p>
        </div>
        <BackendBadge state={backend} />
      </header>

      <StepIndicator current={0} />

      <main className="card">
        <h2>{STEPS[0]}</h2>
        <p className="muted">
          File upload and column detection arrive in Milestone 2. For now this page checks that the
          frontend can reach the backend.
        </p>
      </main>

      <footer className="app-footer">
        Open source &middot; zero-cost stack &middot; no paid AI APIs
      </footer>
    </div>
  );
}

function BackendBadge({ state }: { state: BackendState }) {
  if (state.kind === "checking") return <span className="badge">Checking backend…</span>;
  if (state.kind === "down")
    return <span className="badge badge-error">Backend unreachable</span>;
  return <span className="badge badge-ok">Backend connected · v{state.version}</span>;
}
