// Diverging stacked bars: the standard way to show Likert answers.
// Disagreement extends left of a centre line, agreement right, and the neutral
// share straddles the centre. Comparing the left and right lengths shows the
// balance of opinion at a glance, which a pie chart or stacked 0-100% bar can't.
//
// Built with HTML/CSS instead of Recharts: long item texts (and Arabic) wrap
// naturally above each bar, which SVG axis labels do poorly.
import type { ChoiceCount } from "../../api/types";
import { formatNumber } from "../../format";
import { divergingColors } from "./palette";

export interface LikertRow {
  key: string;
  label: string;
  meta?: string;
  counts: ChoiceCount[];
}

interface Props {
  rows: LikertRow[];
  levels: string[];
}

const TICKS = [0, 25, 50, 75, 100]; // track positions (%): 100% ... 0 ... 100%

export function LikertChart({ rows, levels }: Props) {
  const k = levels.length;
  const colors = divergingColors(k);
  const arm = Math.floor(k / 2);
  const hasMid = k % 2 === 1;

  return (
    <div className="likert">
      <ul className="legend" aria-label="Answer scale">
        {levels.map((level, i) => (
          <li key={level}>
            <span className="swatch" style={{ background: colors[i] }} />
            <span dir="auto">{level}</span>
          </li>
        ))}
      </ul>

      {rows.map((row) => {
        const pct = levels.map((_, i) => row.counts[i]?.percent ?? 0);
        const n = row.counts.reduce((s, c) => s + c.count, 0);
        const negative = pct.slice(0, arm).reduce((a, b) => a + b, 0);
        const positive = pct.slice(k - arm).reduce((a, b) => a + b, 0);
        const middle = hasMid ? pct[arm] : 0;
        // The track spans 100% disagree ... 0 ... 100% agree, so 1 point = 0.5% of its width.
        let left = 50 - (negative + middle / 2) / 2;
        const segments = pct.map((p, i) => {
          const seg = { left, width: p / 2, i, p };
          left += p / 2;
          return seg;
        });
        const visible = segments.filter((s) => s.width > 0);
        return (
          <div className="likert-row" key={row.key}>
            <div className="likert-label" dir="auto">
              {row.label}
              {row.meta && <span className="muted small"> · {row.meta}</span>}
            </div>
            <div className="likert-bar">
              <span className="likert-side likert-neg" title="Share disagreeing">
                {formatNumber(negative, 0)}%
              </span>
              <div
                className="likert-track"
                role="img"
                aria-label={`${row.label}: ${levels
                  .map((l, i) => `${l} ${formatNumber(pct[i], 0)}%`)
                  .join(", ")} (n = ${n})`}
              >
                {TICKS.map((t) => (
                  <span key={t} className={`likert-grid${t === 50 ? " likert-zero" : ""}`} style={{ left: `${t}%` }} />
                ))}
                {visible.map((s, j) => (
                  <span
                    key={s.i}
                    className="likert-seg"
                    title={`${levels[s.i]}: ${formatNumber(s.p, 1)}% (${row.counts[s.i]?.count ?? 0})`}
                    style={{
                      left: `${s.left}%`,
                      width: `${s.width}%`,
                      background: colors[s.i],
                      borderTopLeftRadius: j === 0 ? 4 : 0,
                      borderBottomLeftRadius: j === 0 ? 4 : 0,
                      borderTopRightRadius: j === visible.length - 1 ? 4 : 0,
                      borderBottomRightRadius: j === visible.length - 1 ? 4 : 0,
                    }}
                  />
                ))}
              </div>
              <span className="likert-side likert-pos" title="Share agreeing">
                {formatNumber(positive, 0)}%
              </span>
            </div>
          </div>
        );
      })}

      <div className="likert-axis" aria-hidden="true">
        <span />
        <div className="likert-axis-track">
          {TICKS.map((t) => (
            <span key={t} style={{ left: `${t}%` }}>
              {Math.abs(100 - 2 * t)}%
            </span>
          ))}
        </div>
        <span />
      </div>
    </div>
  );
}

export function LikertTable({ rows, levels }: Props) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Item</th>
          {levels.map((l) => (
            <th key={l} className="num" dir="auto">
              {l}
            </th>
          ))}
          <th className="num">n</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key}>
            <td dir="auto">{row.label}</td>
            {levels.map((l, i) => (
              <td key={l} className="num">
                {formatNumber(row.counts[i]?.percent ?? 0, 1)}%
              </td>
            ))}
            <td className="num">{row.counts.reduce((s, c) => s + c.count, 0)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
