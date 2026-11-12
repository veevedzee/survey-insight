import { useMemo, useState } from "react";
import type { CleaningReport, QualityCheck } from "../api/types";

interface Props {
  report: CleaningReport;
  busy: boolean;
  initiallyApplied?: string[];
  onApply: (keys: string[]) => void;
  onBack: () => void;
}

/** Which responses would be excluded, counting overlaps once. */
export function excludedRows(checks: QualityCheck[], selected: Set<string>): Set<number> {
  const rows = new Set<number>();
  for (const check of checks) {
    if (check.action === "exclude" && check.available && selected.has(check.key)) {
      check.flagged_rows.forEach((r) => rows.add(r));
    }
  }
  return rows;
}

export function CleaningStep({ report, busy, initiallyApplied, onApply, onBack }: Props) {
  const [selected, setSelected] = useState<Set<string>>(
    () =>
      new Set(
        initiallyApplied ??
          report.checks.filter((c) => c.available && c.n_flagged > 0).map((c) => c.key),
      ),
  );

  const excluded = useMemo(() => excludedRows(report.checks, selected), [report, selected]);
  // Responses that keep their row but lose an outlier value.
  const blankedRows = report.checks
    .filter((c) => c.action === "blank" && c.available && selected.has(c.key))
    .reduce((sum, c) => sum + c.n_flagged, 0);
  const kept = report.n_rows - excluded.size;
  const flaggedTotal = report.checks.reduce(
    (sum, c) => sum + (c.action === "exclude" ? c.flagged_rows.length : 0),
    0,
  );

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <section>
      <div className="section-head">
        <h2>Cleaning report</h2>
        <p className="muted">
          Each check below flags responses that could distort the results. Nothing is removed until
          you choose. Untick a check to keep those responses.
        </p>
      </div>

      <div className="before-after" aria-live="polite">
        <div>
          <span className="stat-value">{report.n_rows}</span>
          <span className="stat-label">responses uploaded</span>
        </div>
        <svg width="28" height="28" viewBox="0 0 24 24" aria-hidden="true" className="arrow">
          <path d="M5 12h14m-5-5 5 5-5 5" fill="none" stroke="currentColor" strokeWidth="2" />
        </svg>
        <div>
          <span className="stat-value accent">{kept}</span>
          <span className="stat-label">
            kept for analysis
            {excluded.size > 0 && ` (${excluded.size} excluded)`}
          </span>
        </div>
        <div className="keep-bar" aria-hidden="true">
          <span style={{ width: `${(kept / Math.max(report.n_rows, 1)) * 100}%` }} />
        </div>
        {flaggedTotal > excluded.size && excluded.size > 0 && (
          <p className="muted small">
            Some responses are flagged by more than one check; each is counted once.
          </p>
        )}
      </div>

      <div className="checks">
        {report.checks.map((check) => (
          <CheckCard
            key={check.key}
            check={check}
            checked={selected.has(check.key)}
            onToggle={() => toggle(check.key)}
          />
        ))}
      </div>

      {report.normalizations.length > 0 && (
        <div className="card card-flat">
          <h3>Spelling variants merged automatically</h3>
          <p className="muted small">
            Answers that differ only in capitals or spaces are the same answer. Each was merged into
            its most common spelling so it isn't counted as a separate category.
          </p>
          <ul className="plain-list">
            {report.normalizations.map((n) => (
              <li key={n.column}>
                <span dir="auto">
                  <strong>{n.column}</strong>{" "}
                  <span className="muted">
                    {n.changes
                      .slice(0, 3)
                      .map(([from, to]) => `“${from}” → “${to}”`)
                      .join(", ")}
                  </span>
                </span>
                <span className="muted nowrap">{n.n_changed} answers</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="actions">
        <button type="button" className="button button-ghost" onClick={onBack} disabled={busy}>
          Start over
        </button>
        <span className="muted actions-note">
          {kept} responses
          {blankedRows > 0 &&
            ` · outlier values cleared in ${blankedRows} response${blankedRows > 1 ? "s" : ""}`}
        </span>
        <button
          type="button"
          className="button"
          disabled={busy}
          onClick={() => onApply([...selected])}
        >
          {busy ? "Running statistics…" : "Apply and continue"}
        </button>
      </div>
    </section>
  );
}

function CheckCard({
  check,
  checked,
  onToggle,
}: {
  check: QualityCheck;
  checked: boolean;
  onToggle: () => void;
}) {
  const [open, setOpen] = useState(false);
  const disabled = !check.available || check.n_flagged === 0;
  const verb = check.action === "blank" ? "Clear these values" : "Exclude these responses";

  return (
    <article className={`check${disabled ? " check-disabled" : ""}${checked && !disabled ? " check-on" : ""}`}>
      <div className="check-head">
        <label className="check-toggle">
          <input
            type="checkbox"
            checked={checked && !disabled}
            disabled={disabled}
            onChange={onToggle}
            aria-label={`${verb}: ${check.label}`}
          />
          <span>
            <strong>{check.label}</strong>
            <span className="muted small block">{check.description}</span>
          </span>
        </label>
        <span className={`count-pill${check.n_flagged ? " count-pill-on" : ""}`}>
          {check.available ? check.n_flagged : "n/a"}
        </span>
      </div>

      {!check.available && <p className="muted small check-note">{check.unavailable_reason}</p>}
      {check.available && check.n_flagged === 0 && (
        <p className="muted small check-note">Nothing flagged.</p>
      )}

      {check.available && check.examples.length > 0 && (
        <>
          <button type="button" className="link-button" onClick={() => setOpen((o) => !o)}>
            {open ? "Hide examples" : `Show examples (${Math.min(check.examples.length, 8)})`}
          </button>
          {open && (
            <ul className="example-list">
              {check.examples.map((ex) => (
                <li key={`${ex.row}-${ex.detail}`}>
                  <span className="row-tag">#{ex.row + 1}</span>
                  <span dir="auto">{ex.detail}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </article>
  );
}
