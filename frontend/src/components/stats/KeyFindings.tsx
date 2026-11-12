import type { Finding } from "../../api/types";

const KIND_LABEL: Record<Finding["kind"], string> = {
  difference: "Group difference",
  relationship: "Relationship",
  reliability: "Measurement",
  agreement: "Opinion",
  theme: "Open-ended answers",
  quality: "Data quality",
  custom: "Finding",
};

/**
 * Key findings, written by rules on the computed statistics (findings.py),
 * not by a language model, so each one points to the test behind it.
 */
export function KeyFindings({ findings, loading }: { findings: Finding[] | null; loading: boolean }) {
  if (!findings) {
    return <p className="muted">{loading ? "Summarising the results…" : "No findings available."}</p>;
  }
  return (
    <ol className="findings">
      {findings.map((f, i) => (
        <li key={`${f.kind}-${f.title}`} className={`finding finding-${f.kind}`}>
          <span className="finding-rank" aria-hidden="true">
            {i + 1}
          </span>
          <div>
            <span className="finding-kind">{KIND_LABEL[f.kind]}</span>
            <p dir="auto">{f.text}</p>
            {f.evidence && <p className="finding-evidence">{f.evidence}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
