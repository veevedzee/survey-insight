import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SentimentBadge, sentimentLabel } from "./SentimentBadge";

const negative = {
  n_english: 20,
  mean_compound: -0.31,
  positive_percent: 10,
  neutral_percent: 25,
  negative_percent: 65,
};

describe("SentimentBadge", () => {
  it("turns the score into a plain-English label and says only English was scored", () => {
    render(<SentimentBadge sentiment={negative} />);
    expect(screen.getByText(/Mostly negative \(English only, n = 20\)/)).toBeInTheDocument();
  });

  it("uses the conventional VADER cut-offs", () => {
    expect(sentimentLabel(0.05).text).toBe("Mostly positive");
    expect(sentimentLabel(0.0).text).toBe("Mixed / neutral");
    expect(sentimentLabel(-0.05).text).toBe("Mostly negative");
  });
});
