import { useEffect, useState } from "react";
import {
  ApiError,
  confirmColumns,
  deleteSession,
  getHealth,
  startSampleSession,
  uploadSurvey,
} from "./api/client";
import type { ColumnType, PrivacyReport, UploadResponse } from "./api/types";
import { ColumnsStep } from "./components/ColumnsStep";
import { Logo } from "./components/Logo";
import { PrivacyStep } from "./components/PrivacyStep";
import { StepIndicator } from "./components/StepIndicator";
import { UploadStep } from "./components/UploadStep";

type BackendState = { kind: "checking" } | { kind: "up"; version: string } | { kind: "down" };

// The whole wizard state in one place. Each step only exists once the
// previous one has produced its data, so impossible states can't be represented.
type Wizard =
  | { step: "upload" }
  | { step: "columns"; upload: UploadResponse }
  | { step: "privacy"; upload: UploadResponse; privacy: PrivacyReport };

const STEP_INDEX: Record<Wizard["step"], number> = { upload: 0, columns: 1, privacy: 2 };

export default function App() {
  const [backend, setBackend] = useState<BackendState>({ kind: "checking" });
  const [wizard, setWizard] = useState<Wizard>({ step: "upload" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then((h) => setBackend({ kind: "up", version: h.version }))
      .catch(() => setBackend({ kind: "down" }));
  }, []);

  async function run<T>(action: () => Promise<T>, onDone: (result: T) => void) {
    setBusy(true);
    setError(null);
    try {
      onDone(await action());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
      if (e instanceof ApiError && e.status === 404) setWizard({ step: "upload" });
    } finally {
      setBusy(false);
    }
  }

  function startOver() {
    if (wizard.step !== "upload") deleteSession(wizard.upload.session_id).catch(() => undefined);
    setError(null);
    setWizard({ step: "upload" });
  }

  const onUploaded = (upload: UploadResponse) => setWizard({ step: "columns", upload });

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <Logo />
          <div>
            <span className="brand-name">Survey Insight</span>
            <span className="brand-sub">Open-source survey analytics</span>
          </div>
        </div>
        <BackendBadge state={backend} />
      </header>

      <StepIndicator current={STEP_INDEX[wizard.step]} />

      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      <main className="card card-main">
        {wizard.step === "upload" && (
          <UploadStep
            busy={busy}
            onFile={(file) => run(() => uploadSurvey(file), onUploaded)}
            onSample={() => run(startSampleSession, onUploaded)}
          />
        )}
        {wizard.step === "columns" && (
          <ColumnsStep
            upload={wizard.upload}
            busy={busy}
            onBack={startOver}
            onConfirm={(types: Record<string, ColumnType>) =>
              run(
                () => confirmColumns(wizard.upload.session_id, types),
                (privacy) => setWizard({ step: "privacy", upload: wizard.upload, privacy }),
              )
            }
          />
        )}
        {wizard.step === "privacy" && <PrivacyStep report={wizard.privacy} onBack={startOver} />}
      </main>

      <footer className="app-footer">
        Built with FastAPI, pandas and React &middot; zero-cost, open-source stack &middot; no paid
        AI APIs
      </footer>
    </div>
  );
}

function BackendBadge({ state }: { state: BackendState }) {
  if (state.kind === "checking") return <span className="badge">Connecting…</span>;
  if (state.kind === "down") return <span className="badge badge-error">Server offline</span>;
  return (
    <span className="badge badge-ok" title={`API version ${state.version}`}>
      <span className="dot" /> Server online · v{state.version}
    </span>
  );
}
