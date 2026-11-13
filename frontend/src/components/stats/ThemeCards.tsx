import type { ColumnThemes, ThemesReport } from "../../api/types";
import { formatNumber } from "../../format";
import { SentimentBadge } from "./SentimentBadge";

const LANGUAGE_NAMES: Record<string, string> = { en: "English", ar: "Arabic", mixed: "Mixed" };

export function ThemesSection({ report, loading, error, status, progress, onRetry }: {
  report: ThemesReport | null;
  loading: boolean;
  error: string | null;
  status: string;
  /** 0..1 for the current stage, or null when unknown. */
  progress: number | null;
  onRetry?: () => void;
}) {
  if (error) {
    return (
      <div className="alert alert-actions">
        <span>{error}</span>
        {onRetry && (
          <button type="button" className="button button-secondary" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    );
  }
  if (!report) {
    return (
      <div className="loading-card" role="status">
        <span className="spinner" aria-hidden="true" />
        <div className="loading-body">
          <span>{loading ? status : "No themes yet."}</span>
          {loading && progress !== null && (
            <div className="theme-bar" aria-hidden="true">
              <span style={{ width: `${Math.round(progress * 100)}%` }} />
            </div>
          )}
        </div>
      </div>
    );
  }
  if (report.columns.length === 0) {
    return <p className="muted">This survey has no open-ended questions.</p>;
  }
  return (
    <>
      <p className="muted small">
        Themes are found by meaning, not exact words, using the open-source model{" "}
        <code>{report.model.split("/").pop()}</code>, which understands Arabic and English and ran
        in your browser.{" "}
        {report.sentiment_note}
      </p>
      {report.columns.map((col) => (
        <ColumnThemesBlock key={col.column} col={col} />
      ))}
    </>
  );
}

function ColumnThemesBlock({ col }: { col: ColumnThemes }) {
  return (
    <div className="theme-block">
      <h4 dir="auto">{col.column}</h4>
      <p className="muted small">
        {col.n_used} answers in {col.k > 1 ? `${col.k} themes` : "one group"} · {col.quality}
        {col.silhouette !== null && ` (silhouette ${formatNumber(col.silhouette)})`}
      </p>
      {col.notes.map((n) => (
        <p key={n} className="muted small">
          {n}
        </p>
      ))}
      <div className="theme-grid">
        {col.themes.map((t) => (
          <article key={t.id} className="theme-card">
            <header>
              <h5 dir="auto">{t.label}</h5>
              <span className="theme-size">
                {formatNumber(t.percent, 0)}% <span className="muted small">({t.size})</span>
              </span>
            </header>
            <div className="theme-bar" aria-hidden="true">
              <span style={{ width: `${t.percent}%` }} />
            </div>
            {t.quotes.map((q) => (
              <blockquote key={q.text} dir="auto" className="quote">
                {q.text}
              </blockquote>
            ))}
            <div className="chips">
              {Object.entries(t.languages).map(([lang, n]) => (
                <span key={lang} className="pill">
                  {LANGUAGE_NAMES[lang] ?? lang} {n}
                </span>
              ))}
              <SentimentBadge sentiment={t.sentiment} />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
