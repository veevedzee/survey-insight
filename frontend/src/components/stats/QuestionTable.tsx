import type { QuestionSummary } from "../../api/types";
import { COLUMN_TYPES } from "../../columnTypes";
import { formatNumber } from "../../format";

/** One-line summary per question. The dashboard charts (Milestone 5) expand on this. */
function summarise(q: QuestionSummary): string {
  if (q.likert) {
    return `Median: ${q.likert.median_label} · ${formatNumber(q.likert.agree_percent, 0)}% in the top two levels`;
  }
  if (q.numeric) {
    const n = q.numeric;
    return `Mean ${formatNumber(n.mean)} (SD ${formatNumber(n.sd)}) · median ${formatNumber(n.median)} · range ${formatNumber(n.min)}–${formatNumber(n.max)}`;
  }
  if (q.counts && q.counts.length) {
    const top = q.counts[0];
    const suffix = q.type === "multiple_choice" ? " of respondents" : "";
    return `Most common: ${top.label} (${formatNumber(top.percent, 0)}%${suffix})`;
  }
  return "–";
}

export function QuestionTable({ questions }: { questions: QuestionSummary[] }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Question</th>
            <th>Type</th>
            <th className="num">n</th>
            <th>Summary</th>
          </tr>
        </thead>
        <tbody>
          {questions.map((q) => (
            <tr key={q.column}>
              <td dir="auto" className="col-name">
                {q.label}
              </td>
              <td>
                <span className={`type-chip type-${q.type}`}>{COLUMN_TYPES[q.type].label}</span>
              </td>
              <td className="num">{q.n}</td>
              <td dir="auto">{summarise(q)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
