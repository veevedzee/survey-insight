import { useEffect, useRef, useState } from "react";
import { ApiError, getFindings } from "../api/client";
import type { CleaningResult, Finding, StatsReport, ThemesReport } from "../api/types";
import { computeThemes } from "../embedding/computeThemes";
import { describeProgress, type EmbedProgress } from "../embedding/embeddings";
import { ExportBar } from "./ExportBar";
import { ComparisonCard, CorrelationCard } from "./stats/ComparisonCard";
import { KeyFindings } from "./stats/KeyFindings";
import { QuestionCharts } from "./stats/QuestionCharts";
import { ScaleCard } from "./stats/ScaleCard";
import { ThemesSection } from "./stats/ThemeCards";

interface Props {
  sessionId: string;
  filename: string;
  result: CleaningResult;
  stats: StatsReport;
  onEditCleaning: () => void;
  onBack: () => void;
}

const SECTIONS = [
  { id: "findings", label: "Key findings" },
  { id: "themes", label: "Themes" },
  { id: "differences", label: "Group differences" },
  { id: "relationships", label: "Relationships" },
  { id: "scales", label: "Scales" },
  { id: "questions", label: "All questions" },
];

export function DashboardStep({ sessionId, filename, result, stats, onEditCleaning, onBack }: Props) {
  const dashboardRef = useRef<HTMLElement>(null);
  const [showAll, setShowAll] = useState(false);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [themes, setThemes] = useState<ThemesReport | null>(null);
  const [themesError, setThemesError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState<EmbedProgress | null>(null);

  // Findings from the statistics come back instantly. Themes need the language
  // model, which runs in this browser, so they come after; then the findings
  // are refreshed to include the top theme of each open-ended question.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const quick = await getFindings(sessionId);
        if (!cancelled) setFindings(quick);
        const report = await computeThemes(sessionId, (p) => !cancelled && setProgress(p));
        if (cancelled) return;
        setThemes(report);
        setFindings(await getFindings(sessionId));
      } catch (e) {
        if (!cancelled) {
          setThemesError(
            e instanceof ApiError
              ? e.message
              : "Theme detection failed. The language model may not have downloaded; check your connection and reload.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, result]);
  const significant = stats.comparisons.filter((c) => c.significant);
  const shown = showAll ? stats.comparisons : significant;
  const sigCorrelations = stats.correlations.filter((c) => c.significant);
  const correlations = showAll ? stats.correlations : sigCorrelations;

  return (
    <section className="dashboard" ref={dashboardRef}>
      <div className="section-head results-head">
        <div>
          <h2>Results</h2>
          <p className="muted">
            Based on the {result.n_after} responses kept after cleaning (
            {result.n_before - result.n_after} excluded, {result.n_values_blanked} outlier values
            cleared).
          </p>
        </div>
        <ExportBar
          sessionId={sessionId}
          filename={filename}
          nResponses={result.n_after}
          nExcluded={result.n_before - result.n_after}
          dashboardRef={dashboardRef}
          reportReady={!loading}
        />
      </div>

      <div className="stat-row">
        <Stat value={stats.n_responses} label="responses analysed" />
        <Stat value={stats.scales.filter((s) => s.reliable).length} label="reliable scales" />
        <Stat value={significant.length} label={`significant group differences (of ${stats.comparisons.length})`} />
        <Stat value={sigCorrelations.length} label={`significant relationships (of ${stats.correlations.length})`} />
      </div>

      <nav className="section-nav" aria-label="Dashboard sections">
        {SECTIONS.map((s) => (
          <a key={s.id} href={`#${s.id}`}>
            {s.label}
          </a>
        ))}
        <label className="toggle">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          Include non-significant results
        </label>
      </nav>

      <h3 className="section-title" id="findings">
        Key findings
      </h3>
      <KeyFindings findings={findings} loading={loading} />

      <h3 className="section-title" id="themes">
        Themes in open-ended answers
      </h3>
      <ThemesSection
        report={themes}
        loading={loading}
        error={themesError}
        status={describeProgress(progress)}
        progress={progress && progress.total ? progress.done / progress.total : null}
      />

      <div className="note note-info">
        {stats.notes.map((n) => (
          <p key={n}>{n}</p>
        ))}
      </div>

      <h3 className="section-title" id="differences">
        Group differences
      </h3>
      {shown.length === 0 ? (
        <p className="muted">No significant group differences after correction.</p>
      ) : (
        <div className="results">
          {shown.map((c) => (
            <ComparisonCard key={`${c.group_by}|${c.outcome}`} comparison={c} />
          ))}
        </div>
      )}

      <h3 className="section-title" id="relationships">
        Relationships between numeric answers
      </h3>
      {correlations.length === 0 ? (
        <p className="muted">No significant relationships after correction.</p>
      ) : (
        <div className="results">
          {correlations.map((c) => (
            <CorrelationCard key={`${c.x}|${c.y}`} correlation={c} />
          ))}
        </div>
      )}

      {stats.scales.length > 0 && (
        <>
          <h3 className="section-title" id="scales">
            Scales and reliability
          </h3>
          <div className="grid-2 grid-cards">
            {stats.scales.map((s) => (
              <ScaleCard key={s.name} scale={s} />
            ))}
          </div>
        </>
      )}

      <h3 className="section-title" id="questions">
        Every question
      </h3>
      <QuestionCharts questions={stats.questions} />

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
