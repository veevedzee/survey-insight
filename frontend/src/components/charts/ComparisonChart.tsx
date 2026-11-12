// Picks the right chart for a group comparison, mirroring how the backend
// picked the test: the outcome's type decides.
import type { Comparison } from "../../api/types";
import { formatNumber } from "../../format";
import { CategoryStackChart, CategoryStackTable } from "./CategoryStackChart";
import { LikertChart, LikertTable, type LikertRow } from "./LikertChart";
import { RangeChart } from "./RangeChart";

const MEANS_TESTS = new Set(["Welch's t-test", "One-way ANOVA"]);

function likertRows(c: Comparison): LikertRow[] {
  return [...c.groups]
    .sort((a, b) => (b.mean ?? 0) - (a.mean ?? 0))
    .map((g) => ({ key: g.group, label: g.group, meta: `n = ${g.n}`, counts: g.distribution ?? [] }));
}

export function ComparisonChart({ comparison: c }: { comparison: Comparison }) {
  if (c.outcome_kind === "likert" && c.levels) {
    return <LikertChart rows={likertRows(c)} levels={c.levels} />;
  }
  if (c.outcome_kind === "categorical" && c.levels) {
    return <CategoryStackChart groups={c.groups} levels={c.levels} />;
  }
  if (c.axis_min !== null && c.axis_max !== null) {
    return (
      <RangeChart
        groups={c.groups}
        min={c.axis_min}
        max={c.axis_max}
        centre={MEANS_TESTS.has(c.test) ? "mean" : "median"}
      />
    );
  }
  return null;
}

export function ComparisonTable({ comparison: c }: { comparison: Comparison }) {
  if (c.outcome_kind === "likert" && c.levels) {
    return <LikertTable rows={likertRows(c)} levels={c.levels} />;
  }
  if (c.outcome_kind === "categorical" && c.levels) {
    return <CategoryStackTable groups={c.groups} levels={c.levels} />;
  }
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>{c.group_by}</th>
          <th className="num">n</th>
          <th className="num">Q1</th>
          <th className="num">Median</th>
          <th className="num">Q3</th>
          <th className="num">Mean</th>
        </tr>
      </thead>
      <tbody>
        {c.groups.map((g) => (
          <tr key={g.group}>
            <td dir="auto">{g.group}</td>
            <td className="num">{g.n}</td>
            <td className="num">{formatNumber(g.q1)}</td>
            <td className="num">{formatNumber(g.median)}</td>
            <td className="num">{formatNumber(g.q3)}</td>
            <td className="num">{formatNumber(g.mean)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
