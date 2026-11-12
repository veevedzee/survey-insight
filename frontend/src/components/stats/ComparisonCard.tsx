import { useState } from "react";
import type { Comparison, Correlation } from "../../api/types";
import { formatNumber, formatP } from "../../format";

export function ComparisonCard({ comparison: c }: { comparison: Comparison }) {
  const [open, setOpen] = useState(false);
  const categorical = c.outcome_kind === "categorical";
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
      <button type="button" className="link-button flush" onClick={() => setOpen((o) => !o)}>
        {open ? "Hide details" : "Why this test? · group details"}
      </button>
      {open && (
        <div className="details">
          <p className="small muted">{c.test_reason}</p>
          <table className="data-table">
            <thead>
              <tr>
                <th>{c.group_by}</th>
                <th className="num">n</th>
                {categorical ? (
                  <th className="num">% giving the highlighted answer</th>
                ) : (
                  <>
                    <th className="num">Median</th>
                    <th className="num">Mean</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {c.groups.map((g) => (
                <tr key={g.group}>
                  <td dir="auto">{g.group}</td>
                  <td className="num">{g.n}</td>
                  {categorical ? (
                    <td className="num">{formatNumber(g.percent, 1)}%</td>
                  ) : (
                    <>
                      <td className="num">{formatNumber(g.median)}</td>
                      <td className="num">{formatNumber(g.mean)}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="small muted">
            Unadjusted {formatP(c.p_value)}; test statistic = {formatNumber(c.statistic)}.
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
