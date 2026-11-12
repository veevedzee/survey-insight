// One chart per question, chosen by type. Likert items from the same grid are
// drawn together in one diverging chart so they can be compared directly.
import type { QuestionSummary } from "../../api/types";
import { formatNumber } from "../../format";
import { ChartCard } from "../charts/ChartCard";
import { ChoiceBarChart, ChoiceTable } from "../charts/ChoiceBarChart";
import { Histogram, HistogramTable } from "../charts/Histogram";
import { LikertChart, LikertTable, type LikertRow } from "../charts/LikertChart";

interface LikertBlock {
  key: string;
  title: string;
  items: QuestionSummary[];
}

function groupLikert(questions: QuestionSummary[]): LikertBlock[] {
  const blocks: LikertBlock[] = [];
  const byGroup = new Map<string, LikertBlock>();
  for (const q of questions.filter((q) => q.type === "likert" && q.counts)) {
    const key = q.scale_group ?? q.column;
    let block = byGroup.get(key);
    if (!block) {
      block = { key, title: q.scale_group ?? q.label, items: [] };
      byGroup.set(key, block);
      blocks.push(block);
    }
    block.items.push(q);
  }
  return blocks;
}

function levelsOf(items: QuestionSummary[]): string[] {
  return (items[0].counts ?? []).map((c) => c.label);
}

export function QuestionCharts({ questions }: { questions: QuestionSummary[] }) {
  const likert = groupLikert(questions);
  const others = questions.filter((q) => q.type !== "likert");

  return (
    <>
      {likert.map((block) => {
        const levels = levelsOf(block.items);
        const rows: LikertRow[] = block.items
          .filter((q) => (q.counts ?? []).length === levels.length)
          .map((q) => ({
            key: q.column,
            label: block.items.length > 1 ? q.label : "All responses",
            meta: `n = ${q.n}`,
            counts: q.counts ?? [],
          }));
        const agreeShare = (r: LikertRow) =>
          r.counts.slice(levels.length - Math.floor(levels.length / 2)).reduce((s, c) => s + c.percent, 0);
        rows.sort((a, b) => agreeShare(b) - agreeShare(a));
        return (
          <ChartCard
            key={block.key}
            wide
            title={block.title}
            meta={block.items.length > 1 ? `${block.items.length} items, sorted by agreement` : `n = ${block.items[0].n}`}
            table={<LikertTable rows={rows} levels={levels} />}
          >
            <LikertChart rows={rows} levels={levels} />
          </ChartCard>
        );
      })}

      <div className="chart-grid">
        {others.map((q) => {
          if (q.numeric) {
            const n = q.numeric;
            return (
              <ChartCard
                key={q.column}
                title={q.label}
                meta={`n = ${q.n} · median ${formatNumber(n.median)} · mean ${formatNumber(n.mean)} (SD ${formatNumber(n.sd)})`}
                table={<HistogramTable summary={n} />}
              >
                <Histogram summary={n} />
              </ChartCard>
            );
          }
          if (q.counts && q.counts.length) {
            const percentOf = q.type === "multiple_choice" ? "respondents" : "answers";
            return (
              <ChartCard
                key={q.column}
                title={q.label}
                meta={
                  q.type === "multiple_choice"
                    ? `n = ${q.n} · several answers allowed, so shares add up to more than 100%`
                    : `n = ${q.n}`
                }
                table={<ChoiceTable counts={q.counts} percentOf={percentOf} />}
              >
                <ChoiceBarChart counts={q.counts} percentOf={percentOf} />
              </ChartCard>
            );
          }
          return null;
        })}
      </div>
    </>
  );
}
