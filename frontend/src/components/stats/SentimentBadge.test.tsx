import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SentimentBadge } from "./SentimentBadge";

const negative = {
  n_english: 20,
  mean_compound: -0.31,
  positive_percent: 10,
  neutral_percent: 25,
  negative_percent: 65,
};

describe("SentimentBadge", () => {
  it("always says that only English answers were scored", () => {
    render(<SentimentBadge sentiment={negative} />);
    expect(screen.getByText(/English only, n = 20/)).toBeInTheDocument();
  });

  // TODO(you): change `it.skip` to `it` once SentimentBadge shows a label.
  it.skip("turns the score into a plain-English label", () => {
    render(<SentimentBadge sentiment={negative} />);
    expect(screen.getByText(/Mostly negative/)).toBeInTheDocument();
  });
});
