import type { CleaningResult } from "../api/types";

interface Props {
  result: CleaningResult;
  onEditCleaning: () => void;
  onBack: () => void;
}

// Placeholder until Milestone 4/5: confirms what the analysis will run on.
export function DashboardStep({ result, onEditCleaning, onBack }: Props) {
  const excluded = result.n_before - result.n_after;
  return (
    <section>
      <div className="section-head">
        <h2>Ready for analysis</h2>
        <p className="muted">
          The statistics and charts run on the {result.n_after} responses you kept.
        </p>
      </div>
      <div className="stat-row">
        <div className="stat">
          <span className="stat-value">{result.n_after}</span>
          <span className="stat-label">responses analysed</span>
        </div>
        <div className="stat">
          <span className="stat-value">{excluded}</span>
          <span className="stat-label">responses excluded</span>
        </div>
        <div className="stat">
          <span className="stat-value">{result.n_values_blanked}</span>
          <span className="stat-label">outlier values cleared</span>
        </div>
      </div>
      <div className="note">Statistics arrive in Milestone 4 and the dashboard charts in Milestone 5.</div>
      <div className="actions">
        <button type="button" className="button button-ghost" onClick={onBack}>
          Start over
        </button>
        <span className="actions-note" />
        <button type="button" className="button button-secondary" onClick={onEditCleaning}>
          Change cleaning choices
        </button>
      </div>
    </section>
  );
}
