// Sorted horizontal bars for single- and multiple-choice questions.
// Horizontal so long answer labels stay readable; sorted so the ranking is
// the first thing you see; one colour because the bars are one series.
import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChoiceCount } from "../../api/types";
import { formatNumber } from "../../format";
import { useChartColors } from "./palette";

const MAX_BARS = 12;

/**
 * Ordered categories ("1st year", "2nd year", "18-24") read best in their own
 * order; everything else is sorted by frequency so the ranking is visible.
 * We treat a question as ordered when every answer contains a number.
 */
export function sortChoices(counts: ChoiceCount[]): ChoiceCount[] {
  const firstNumber = (s: string) => Number(s.match(/\d+(\.\d+)?/)?.[0]);
  const ordered = counts.length > 1 && counts.every((c) => !Number.isNaN(firstNumber(c.label)));
  return [...counts].sort((a, b) =>
    ordered ? firstNumber(a.label) - firstNumber(b.label) : b.count - a.count,
  );
}

export function ChoiceBarChart({ counts, percentOf }: { counts: ChoiceCount[]; percentOf: string }) {
  const colors = useChartColors();
  const sorted = sortChoices(counts);
  const data =
    sorted.length > MAX_BARS
      ? [
          ...sorted.slice(0, MAX_BARS - 1),
          sorted.slice(MAX_BARS - 1).reduce(
            (acc, c) => ({ label: "Other", count: acc.count + c.count, percent: acc.percent + c.percent }),
            { label: "Other", count: 0, percent: 0 },
          ),
        ]
      : sorted;
  const longest = Math.max(...data.map((d) => d.label.length));
  const labelWidth = Math.min(180, Math.max(70, longest * 7));

  return (
    <div style={{ width: "100%", height: data.length * 34 + 16 }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 48, bottom: 4, left: 4 }} barCategoryGap={6}>
          <XAxis type="number" hide domain={[0, "dataMax"]} />
          <YAxis
            type="category"
            dataKey="label"
            width={labelWidth}
            tickLine={false}
            axisLine={{ stroke: colors.axis }}
            tick={{ fill: colors.text, fontSize: 12 }}
            tickFormatter={(v: string) => (v.length > 26 ? `${v.slice(0, 25)}…` : v)}
          />
          <Tooltip
            cursor={{ fill: colors.grid, opacity: 0.5 }}
            contentStyle={{ background: colors.surface, border: `1px solid ${colors.axis}`, borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: colors.text, fontWeight: 600 }}
            formatter={(value, _name, item) => [
              `${value} (${formatNumber((item.payload as ChoiceCount).percent, 1)}% of ${percentOf})`,
              "Answers",
            ]}
          />
          <Bar dataKey="count" fill={colors.series1} radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive={false}>
            <LabelList
              dataKey="percent"
              position="right"
              formatter={(v) => `${formatNumber(Number(v), 0)}%`}
              style={{ fill: colors.muted, fontSize: 12 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ChoiceTable({ counts, percentOf }: { counts: ChoiceCount[]; percentOf: string }) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Answer</th>
          <th className="num">Count</th>
          <th className="num">% of {percentOf}</th>
        </tr>
      </thead>
      <tbody>
        {counts.map((c) => (
          <tr key={c.label}>
            <td dir="auto">{c.label}</td>
            <td className="num">{c.count}</td>
            <td className="num">{formatNumber(c.percent, 1)}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
