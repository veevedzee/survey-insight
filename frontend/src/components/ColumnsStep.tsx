import { useMemo, useState } from "react";
import type { ColumnProfile, ColumnType, UploadResponse } from "../api/types";
import { COLUMN_TYPES, TYPE_ORDER, shortColumnName } from "../columnTypes";

interface Props {
  upload: UploadResponse;
  busy: boolean;
  onConfirm: (types: Record<string, ColumnType>) => void;
  onBack: () => void;
}

export function ColumnsStep({ upload, busy, onConfirm, onBack }: Props) {
  const [types, setTypes] = useState<Record<string, ColumnType>>(() =>
    Object.fromEntries(upload.columns.map((c) => [c.name, c.detected_type])),
  );

  const counts = useMemo(() => {
    const result: Partial<Record<ColumnType, number>> = {};
    for (const t of Object.values(types)) result[t] = (result[t] ?? 0) + 1;
    return result;
  }, [types]);

  const nChanged = upload.columns.filter((c) => types[c.name] !== c.detected_type).length;

  return (
    <section>
      <div className="section-head">
        <div>
          <h2>Check the column types</h2>
          <p className="muted">
            We read <strong>{upload.n_rows}</strong> responses and <strong>{upload.n_columns}</strong>{" "}
            columns from <em>{upload.filename}</em>. Each type decides which charts and tests are
            used, so fix anything that looks wrong.
          </p>
        </div>
      </div>

      <div className="type-summary">
        {TYPE_ORDER.filter((t) => counts[t]).map((t) => (
          <span key={t} className={`type-chip type-${t}`}>
            {COLUMN_TYPES[t].label} <b>{counts[t]}</b>
          </span>
        ))}
      </div>

      <div className="table-wrap">
        <table className="columns-table">
          <thead>
            <tr>
              <th>Question</th>
              <th>Type</th>
              <th>Why we think so</th>
              <th>Examples</th>
              <th className="num">Missing</th>
            </tr>
          </thead>
          <tbody>
            {upload.columns.map((col) => (
              <ColumnRow
                key={col.name}
                column={col}
                value={types[col.name]}
                total={upload.n_rows}
                onChange={(t) => setTypes((prev) => ({ ...prev, [col.name]: t }))}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="actions">
        <button type="button" className="button button-ghost" onClick={onBack} disabled={busy}>
          Start over
        </button>
        <span className="muted actions-note">
          {nChanged > 0 ? `${nChanged} type${nChanged > 1 ? "s" : ""} changed · ` : ""}
          {counts.identifier ?? 0} personal-data column{counts.identifier === 1 ? "" : "s"} will be
          removed
        </span>
        <button type="button" className="button" onClick={() => onConfirm(types)} disabled={busy}>
          {busy ? "Removing personal data…" : "Confirm and remove personal data"}
        </button>
      </div>
    </section>
  );
}

function ColumnRow({
  column,
  value,
  total,
  onChange,
}: {
  column: ColumnProfile;
  value: ColumnType;
  total: number;
  onChange: (t: ColumnType) => void;
}) {
  const changed = value !== column.detected_type;
  const missingPct = total ? Math.round((column.n_missing / total) * 100) : 0;
  return (
    <tr className={changed ? "row-changed" : undefined}>
      <td className="col-name">
        <span dir="auto">{shortColumnName(column.name, column.scale_group)}</span>
        {column.scale_group && (
          <span className="scale-group" title={column.scale_group}>
            Scale: {column.scale_group}
          </span>
        )}
      </td>
      <td>
        <select
          className={`type-select type-${value}`}
          value={value}
          aria-label={`Type of ${column.name}`}
          onChange={(e) => onChange(e.target.value as ColumnType)}
        >
          {TYPE_ORDER.map((t) => (
            <option key={t} value={t}>
              {COLUMN_TYPES[t].label}
            </option>
          ))}
        </select>
        {changed && <span className="changed-note">was {COLUMN_TYPES[column.detected_type].label}</span>}
      </td>
      <td className="muted reason">{column.reason}</td>
      <td className="examples">
        {column.examples.slice(0, 3).map((ex) => (
          <span key={ex} className="example" dir="auto" title={ex}>
            {ex}
          </span>
        ))}
      </td>
      <td className="num muted">{missingPct}%</td>
    </tr>
  );
}
