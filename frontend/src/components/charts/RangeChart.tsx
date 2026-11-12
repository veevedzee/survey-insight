// Range plot for numeric outcomes by group: the band is the middle half of
// answers (Q1 to Q3) and the dot is the median (or the mean, when a means-based
// test was used). Showing spread stops readers mistaking a small shift in the
// middle for "everyone in group A scores higher".
import type { GroupStat } from "../../api/types";
import { formatNumber } from "../../format";

interface Props {
  groups: GroupStat[];
  min: number;
  max: number;
  centre: "median" | "mean";
}

/** About five round tick values between min and max. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  const span = max - min || 1;
  const raw = span / (count - 1);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? raw;
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 1e-9; v += step) ticks.push(Number(v.toFixed(10)));
  return ticks;
}

export function RangeChart({ groups, min, max, centre }: Props) {
  const ordered = [...groups].sort((a, b) => (b[centre] ?? 0) - (a[centre] ?? 0));
  const pos = (v: number | null | undefined) =>
    v === null || v === undefined ? 0 : ((v - min) / (max - min || 1)) * 100;
  const ticks = niceTicks(min, max);

  return (
    <div className="range-chart">
      <ul className="legend">
        <li>
          <span className="swatch swatch-band" /> middle half of answers (Q1–Q3)
        </li>
        <li>
          <span className="swatch swatch-dot" /> {centre}
        </li>
      </ul>
      {ordered.map((g) => (
        <div className="range-row" key={g.group}>
          <div className="stack-label" dir="auto">
            {g.group} <span className="muted small">n = {g.n}</span>
          </div>
          <div className="range-line">
            <div
              className="range-track"
              role="img"
              aria-label={`${g.group}: ${centre} ${formatNumber(g[centre])}, middle half ${formatNumber(g.q1)} to ${formatNumber(g.q3)}`}
            >
              {ticks.map((t) => (
                <span key={t} className="likert-grid" style={{ left: `${pos(t)}%` }} />
              ))}
              <span
                className="range-band"
                style={{ left: `${pos(g.q1)}%`, width: `${Math.max(pos(g.q3) - pos(g.q1), 0.8)}%` }}
              />
              <span className="range-dot" style={{ left: `${pos(g[centre])}%` }} />
            </div>
            <span className="range-value">{formatNumber(g[centre])}</span>
          </div>
        </div>
      ))}
      <div className="range-axis" aria-hidden="true">
        <span />
        <div className="range-axis-row">
          <div className="likert-axis-track">
            {ticks.map((t) => (
              <span key={t} style={{ left: `${pos(t)}%` }}>
                {formatNumber(t, 1)}
              </span>
            ))}
          </div>
          <span className="range-value" />
        </div>
      </div>
    </div>
  );
}
