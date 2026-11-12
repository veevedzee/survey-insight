// 100% stacked bars: how each group splits across the categories of another
// question (e.g. living situation within each faculty). Every group's bar has
// the same total, so you compare shares, not group sizes; n is shown beside it.
import type { GroupStat } from "../../api/types";
import { formatNumber } from "../../format";
import { MAX_CATEGORIES, categoricalVar, inkOnCategorical } from "./palette";

const LABEL_MIN_PERCENT = 12; // only label segments wide enough to fit the text

export function CategoryStackChart({ groups, levels }: { groups: GroupStat[]; levels: string[] }) {
  // Past eight categories, fold the tail into "Other" instead of inventing colours.
  const shown = levels.length > MAX_CATEGORIES ? [...levels.slice(0, MAX_CATEGORIES - 1), "Other"] : levels;
  const share = (g: GroupStat, level: string) => {
    if (level === "Other" && levels.length > MAX_CATEGORIES) {
      return (g.distribution ?? [])
        .filter((d) => !shown.slice(0, -1).includes(d.label))
        .reduce((s, d) => s + d.percent, 0);
    }
    return g.distribution?.find((d) => d.label === level)?.percent ?? 0;
  };

  return (
    <div className="stack-chart">
      <ul className="legend">
        {shown.map((level, i) => (
          <li key={level}>
            <span className="swatch" style={{ background: categoricalVar(i) }} />
            <span dir="auto">{level}</span>
          </li>
        ))}
      </ul>
      {groups.map((g) => (
        <div className="stack-row" key={g.group}>
          <div className="stack-label" dir="auto">
            {g.group} <span className="muted small">n = {g.n}</span>
          </div>
          <div
            className="stack-track"
            role="img"
            aria-label={`${g.group}: ${shown.map((l) => `${l} ${formatNumber(share(g, l), 0)}%`).join(", ")}`}
          >
            {shown.map((level, i) => {
              const p = share(g, level);
              if (p <= 0) return null;
              return (
                <span
                  key={level}
                  className="stack-seg"
                  title={`${level}: ${formatNumber(p, 1)}%`}
                  style={{ width: `${p}%`, background: categoricalVar(i), color: inkOnCategorical(i) }}
                >
                  {p >= LABEL_MIN_PERCENT ? `${formatNumber(p, 0)}%` : ""}
                </span>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

export function CategoryStackTable({ groups, levels }: { groups: GroupStat[]; levels: string[] }) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Group</th>
          {levels.map((l) => (
            <th key={l} className="num" dir="auto">
              {l}
            </th>
          ))}
          <th className="num">n</th>
        </tr>
      </thead>
      <tbody>
        {groups.map((g) => (
          <tr key={g.group}>
            <td dir="auto">{g.group}</td>
            {levels.map((l) => (
              <td key={l} className="num">
                {formatNumber(g.distribution?.find((d) => d.label === l)?.percent ?? 0, 1)}%
              </td>
            ))}
            <td className="num">{g.n}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
