import type { SentimentSummary } from "../../api/types";
import { formatNumber } from "../../format";

/**
 * Sentiment of the English answers in a theme (VADER).
 *
 * TODO(you): make this friendlier. Right now it prints the raw average
 * compound score. Turn it into a label a non-statistician understands:
 *   - mean_compound >= 0.05  -> "Mostly positive"
 *   - mean_compound <= -0.05 -> "Mostly negative"
 *   - otherwise              -> "Mixed / neutral"
 * and give each label its own class (e.g. "sentiment-positive") so styles.css
 * can colour it. Keep the "(English only, n = …)" part: it stops readers
 * assuming Arabic answers were scored.
 * Then change `it.skip` to `it` in SentimentBadge.test.tsx.
 */
export function SentimentBadge({ sentiment }: { sentiment: SentimentSummary | null }) {
  if (!sentiment) {
    return <span className="pill">No English answers to score</span>;
  }
  return (
    <span className="pill" title={`${sentiment.positive_percent}% positive, ${sentiment.negative_percent}% negative`}>
      Sentiment {formatNumber(sentiment.mean_compound)} (English only, n = {sentiment.n_english})
    </span>
  );
}
