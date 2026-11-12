// Histogram for numeric answers, with the median marked.
// Each bar is a bin of the value range and its height is how many people
// answered within it. Bars touch (2px gap) because the bins are contiguous.
// Binning happens on the backend: one bin per value for small whole numbers,
// numpy's "auto" rule otherwise.
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HistogramBin, NumericSummary } from "../../api/types";
import { formatNumber } from "../../format";
import { useChartColors } from "./palette";

function binLabel(b: HistogramBin, discrete: boolean): string {
  return discrete ? formatNumber(b.start) : `${formatNumber(b.start)}–${formatNumber(b.end)}`;
}

export function Histogram({ summary }: { summary: NumericSummary }) {
  const colors = useChartColors();
  const bins = summary.histogram;
  const data = bins.map((b) => ({ label: binLabel(b, summary.discrete), count: b.count }));
  const medianBin = bins.findIndex((b, i) =>
    i === bins.length - 1 ? summary.median <= b.end : summary.median >= b.start && summary.median < b.end,
  );

  return (
    <div style={{ width: "100%", height: 220 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 18, right: 12, bottom: 4, left: -16 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke={colors.grid} />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={{ stroke: colors.axis }}
            tick={{ fill: colors.muted, fontSize: 11 }}
            interval="preserveStartEnd"
            minTickGap={8}
          />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: colors.muted, fontSize: 11 }} />
          <Tooltip
            cursor={{ fill: colors.grid, opacity: 0.5 }}
            contentStyle={{ background: colors.surface, border: `1px solid ${colors.axis}`, borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: colors.text, fontWeight: 600 }}
            formatter={(v) => [`${v} people`, "Answers"]}
          />
          <Bar dataKey="count" fill={colors.series1} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          {medianBin >= 0 && (
            <ReferenceLine
              x={data[medianBin].label}
              stroke={colors.text}
              strokeWidth={1.5}
              label={{ value: `median ${formatNumber(summary.median)}`, position: "top", fill: colors.text, fontSize: 11 }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function HistogramTable({ summary }: { summary: NumericSummary }) {
  const unitBins = summary.discrete;
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>{unitBins ? "Value" : "Range"}</th>
          <th className="num">Count</th>
        </tr>
      </thead>
      <tbody>
        {summary.histogram.map((b) => (
          <tr key={b.start}>
            <td>{binLabel(b, unitBins)}</td>
            <td className="num">{b.count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
