import type { PrivacyReport } from "../api/types";

const KIND_LABELS: Record<string, [singular: string, plural: string]> = {
  email: ["email", "emails"],
  phone: ["phone number", "phone numbers"],
  id: ["ID number", "ID numbers"],
  name: ["name", "names"],
};

function kindLabel(kind: string, n: number): string {
  const labels = KIND_LABELS[kind];
  if (!labels) return kind;
  return n === 1 ? labels[0] : labels[1];
}

interface Props {
  report: PrivacyReport;
  busy: boolean;
  onContinue: () => void;
  onBack: () => void;
}

export function PrivacyStep({ report, busy, onContinue, onBack }: Props) {
  return (
    <section>
      <div className="section-head">
        <div>
          <h2>Personal data removed</h2>
          <p className="muted">
            This happened before any analysis. The original upload, which still contained this
            data, has now been deleted from memory.
          </p>
        </div>
      </div>

      <div className="stat-row">
        <Stat
          value={report.removed_columns.length}
          label={report.removed_columns.length === 1 ? "column removed" : "columns removed"}
        />
        <Stat value={report.total_masked} label="values masked in answers" />
        <Stat value={report.n_rows} label="responses kept" />
        <Stat value={report.n_columns} label="columns left to analyse" />
      </div>

      <div className="grid-2">
        <div className="card">
          <h3>Removed columns</h3>
          {report.removed_columns.length === 0 ? (
            <p className="muted">No personal-data columns were found.</p>
          ) : (
            <ul className="plain-list">
              {report.removed_columns.map((c) => (
                <li key={c.name}>
                  <span dir="auto">{c.name}</span>
                  <span className="muted">{c.n_values} values</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <h3>Masked inside written answers</h3>
          {report.masked_columns.length === 0 ? (
            <p className="muted">No personal data was found inside free-text answers.</p>
          ) : (
            report.masked_columns.map((c) => (
              <div key={c.name} className="masked-col">
                <p className="masked-col-name" dir="auto">
                  {c.name}
                </p>
                <div className="type-summary">
                  {Object.entries(c.counts).map(([kind, n]) => (
                    <span key={kind} className="type-chip type-identifier">
                      {n} {kindLabel(kind, n)}
                    </span>
                  ))}
                </div>
                {c.examples.map((ex) => (
                  <blockquote key={ex} dir="auto">
                    {ex}
                  </blockquote>
                ))}
              </div>
            ))
          )}
        </div>
      </div>

      <div className="note">
        <strong>Limits of automatic detection</strong>
        <ul>
          {report.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </div>

      <div className="actions">
        <button type="button" className="button button-ghost" onClick={onBack} disabled={busy}>
          Start over
        </button>
        <span className="actions-note" />
        <button type="button" className="button" onClick={onContinue} disabled={busy}>
          {busy ? "Checking data quality…" : "Continue to cleaning"}
        </button>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
