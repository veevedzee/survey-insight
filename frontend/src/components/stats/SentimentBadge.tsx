import type { SentimentSummary } from "../../api/types";

/**
 * Sentiment of the English answers in a theme (VADER), in plain words.
 * Conventional cut-offs on the average compound score: >= 0.05 positive,
 * <= -0.05 negative. "(English only, n = …)" stops readers assuming Arabic
 * answers were scored.
 */
export function sentimentLabel(mean: number): { text: string; tone: "positive" | "negative" | "neutral" } {
  if (mean >= 0.05) return { text: "Mostly positive", tone: "positive" };
  if (mean <= -0.05) return { text: "Mostly negative", tone: "negative" };
  return { text: "Mixed / neutral", tone: "neutral" };
}

export function SentimentBadge({ sentiment }: { sentiment: SentimentSummary | null }) {
  if (!sentiment) {
    return <span className="pill">No English answers to score</span>;
  }
  const { text, tone } = sentimentLabel(sentiment.mean_compound);
  return (
    <span
      className={`pill sentiment-${tone}`}
      title={`${sentiment.positive_percent}% positive, ${sentiment.negative_percent}% negative (average score ${sentiment.mean_compound.toFixed(2)})`}
    >
      {text} (English only, n = {sentiment.n_english})
    </span>
  );
}
