import { useEffect, useState } from "react";
import {
  ApiError,
  applyCleaning,
  confirmColumns,
  deleteSession,
  getCleaningReport,
  getHealth,
  startSampleSession,
  uploadSurvey,
} from "./api/client";
import type {
  CleaningReport,
  CleaningResult,
  ColumnType,
  PrivacyReport,
  UploadResponse,
} from "./api/types";
import { CleaningStep } from "./components/CleaningStep";
import { ColumnsStep } from "./components/ColumnsStep";
import { DashboardStep } from "./components/DashboardStep";
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
  | { step: "privacy"; upload: UploadResponse; privacy: PrivacyReport }
  | {
      step: "cleaning";
      upload: UploadResponse;
      privacy: PrivacyReport;
      cleaning: CleaningReport;
      applied?: string[];
    }
  | {
      step: "dashboard";
      upload: UploadResponse;
      privacy: PrivacyReport;
      cleaning: CleaningReport;
      result: CleaningResult;
    };

const STEP_INDEX: Record<Wizard["step"], number> = {
  upload: 0,
  columns: 1,
  privacy: 2,
  cleaning: 3,
  dashboard: 4,
};

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

  // Scroll to the top whenever the step changes.
  useEffect(() => {
    window.scrollTo?.({ top: 0, behavior: "smooth" });
  }, [wizard.step]);

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

  function renderStep() {
    switch (wizard.step) {
      case "upload":
        return (
          <UploadStep
            busy={busy}
            onFile={(file) => run(() => uploadSurvey(file), onUploaded)}
            onSample={() => run(startSampleSession, onUploaded)}
          />
        );
      case "columns":
        return (
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
        );
      case "privacy":
        return (
          <PrivacyStep
            report={wizard.privacy}
            busy={busy}
            onBack={startOver}
            onContinue={() =>
              run(
                () => getCleaningReport(wizard.upload.session_id),
                (cleaning) => setWizard({ ...wizard, step: "cleaning", cleaning }),
              )
            }
          />
        );
      case "cleaning":
        return (
          <CleaningStep
            report={wizard.cleaning}
            busy={busy}
            initiallyApplied={wizard.applied}
            onBack={startOver}
            onApply={(keys) =>
              run(
                () => applyCleaning(wizard.upload.session_id, keys),
                (result) =>
                  setWizard({
                    step: "dashboard",
                    upload: wizard.upload,
                    privacy: wizard.privacy,
                    cleaning: wizard.cleaning,
                    result,
                  }),
              )
            }
          />
        );
      case "dashboard":
        return (
          <DashboardStep
            result={wizard.result}
            onBack={startOver}
            onEditCleaning={() =>
              setWizard({
                step: "cleaning",
                upload: wizard.upload,
                privacy: wizard.privacy,
                cleaning: wizard.cleaning,
                applied: wizard.result.applied,
              })
            }
          />
        );
    }
  }

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

      <main className="card card-main">{renderStep()}</main>

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
