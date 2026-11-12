import { useState } from "react";
import type { Comparison, Correlation } from "../../api/types";
import { formatNumber, formatP } from "../../format";
import { ComparisonChart, ComparisonTable } from "../charts/ComparisonChart";

export function ComparisonCard({ comparison: c }: { comparison: Comparison }) {
  const [open, setOpen] = useState(false);
  const [showTable, setShowTable] = useState(false);
  return (
    <article className={`result-card${c.significant ? " result-sig" : ""}`}>
      <p className="sentence" dir="auto">
        {c.sentence}
      </p>
      <div className="chips">
        <span className={`pill ${c.significant ? "pill-ok" : ""}`}>
          {c.significant ? "Significant" : "Not significant"}
        </span>
        <span className="pill">{c.test}</span>
        <span className="pill">{formatP(c.p_adjusted)} (adj.)</span>
        <span className="pill">
          {c.effect_name} = {formatNumber(c.effect_size)} · {c.effect_label}
        </span>
        <span className="pill">n = {c.n_total}</span>
      </div>
      {c.warnings.map((w) => (
        <p key={w} className="small warning-inline">
          {w}
        </p>
      ))}

      <div className="result-chart">
        {showTable ? (
          <div className="table-wrap">
            <ComparisonTable comparison={c} />
          </div>
        ) : (
          <ComparisonChart comparison={c} />
        )}
      </div>

      <div className="card-links">
        <button type="button" className="link-button flush" onClick={() => setOpen((o) => !o)}>
          {open ? "Hide why" : "Why this test?"}
        </button>
        <button
          type="button"
          className="link-button flush"
          onClick={() => setShowTable((s) => !s)}
          aria-pressed={showTable}
        >
          {showTable ? "Show chart" : "Show table"}
        </button>
      </div>
      {open && (
        <div className="details">
          <p className="small muted">{c.test_reason}</p>
          <p className="small muted">
            Unadjusted {formatP(c.p_value)}; test statistic = {formatNumber(c.statistic)}. The
            adjusted p-value accounts for every test run on this survey.
          </p>
        </div>
      )}
    </article>
  );
}

export function CorrelationCard({ correlation: c }: { correlation: Correlation }) {
  return (
    <article className={`result-card${c.significant ? " result-sig" : ""}`}>
      <p className="sentence" dir="auto">
        {c.sentence}
      </p>
      <div className="chips">
        <span className={`pill ${c.significant ? "pill-ok" : ""}`}>
          {c.significant ? "Significant" : "Not significant"}
        </span>
        <span className="pill">Spearman ρ = {formatNumber(c.rho)} · {c.effect_label}</span>
        <span className="pill">{formatP(c.p_adjusted)} (adj.)</span>
        <span className="pill">n = {c.n}</span>
      </div>
    </article>
  );
}
