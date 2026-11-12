import { useState } from "react";
import type { CleaningResult, StatsReport } from "../api/types";
import { ComparisonCard, CorrelationCard } from "./stats/ComparisonCard";
import { QuestionTable } from "./stats/QuestionTable";
import { ScaleCard } from "./stats/ScaleCard";

interface Props {
  result: CleaningResult;
  stats: StatsReport;
  onEditCleaning: () => void;
  onBack: () => void;
}

export function DashboardStep({ result, stats, onEditCleaning, onBack }: Props) {
  const [showAll, setShowAll] = useState(false);
  const significant = stats.comparisons.filter((c) => c.significant);
  const shown = showAll ? stats.comparisons : significant;
  const sigCorrelations = stats.correlations.filter((c) => c.significant);
  const correlations = showAll ? stats.correlations : sigCorrelations;

  return (
    <section>
      <div className="section-head">
        <h2>Results</h2>
        <p className="muted">
          Based on the {result.n_after} responses kept after cleaning (
          {result.n_before - result.n_after} excluded, {result.n_values_blanked} outlier values
          cleared).
        </p>
      </div>

      <div className="stat-row">
        <Stat value={stats.n_responses} label="responses analysed" />
        <Stat value={stats.scales.filter((s) => s.reliable).length} label="reliable scales" />
        <Stat value={significant.length} label={`significant group differences of ${stats.comparisons.length}`} />
        <Stat value={sigCorrelations.length} label={`significant relationships of ${stats.correlations.length}`} />
      </div>

      <div className="note note-info">
        {stats.notes.map((n) => (
          <p key={n}>{n}</p>
        ))}
      </div>

      {stats.scales.length > 0 && (
        <>
          <h3 className="section-title">Scales and reliability</h3>
          <div className="grid-2 grid-cards">
            {stats.scales.map((s) => (
              <ScaleCard key={s.name} scale={s} />
            ))}
          </div>
        </>
      )}

      <div className="section-title-row">
        <h3 className="section-title">Group differences</h3>
        <label className="toggle">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          Show non-significant results too
        </label>
      </div>
      {shown.length === 0 ? (
        <p className="muted">No significant group differences after correction.</p>
      ) : (
        <div className="results">
          {shown.map((c) => (
            <ComparisonCard key={`${c.group_by}|${c.outcome}`} comparison={c} />
          ))}
        </div>
      )}

      <h3 className="section-title">Relationships between numeric answers</h3>
      {correlations.length === 0 ? (
        <p className="muted">No significant relationships after correction.</p>
      ) : (
        <div className="results">
          {correlations.map((c) => (
            <CorrelationCard key={`${c.x}|${c.y}`} correlation={c} />
          ))}
        </div>
      )}

      <h3 className="section-title">Every question at a glance</h3>
      <QuestionTable questions={stats.questions} />

      <div className="note">Charts for each question arrive in Milestone 5.</div>

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

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
