import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Comparison } from "../../api/types";
import { formatP } from "../../format";
import { ComparisonCard } from "./ComparisonCard";

const comparison: Comparison = {
  outcome: "Stress [I worry about my grades]",
  outcome_label: "I worry about my grades",
  outcome_kind: "likert",
  group_by: "Faculty",
  test: "Kruskal-Wallis H",
  test_reason: "4 groups, ordinal or non-normal data: compares ranks.",
  statistic: 21.5,
  p_value: 0.0001,
  p_adjusted: 0.006,
  significant: true,
  effect_name: "epsilon²",
  effect_size: 0.08,
  effect_label: "medium",
  n_total: 259,
  groups: [
    {
      group: "Engineering",
      n: 87,
      median: 4,
      mean: 3.9,
      q1: 3,
      q3: 5,
      percent: null,
      distribution: [
        { label: "Disagree", count: 17, percent: 19.5 },
        { label: "Neutral", count: 20, percent: 23 },
        { label: "Agree", count: 50, percent: 57.5 },
      ],
    },
    {
      group: "Computer Science",
      n: 66,
      median: 3,
      mean: 3.1,
      q1: 2,
      q3: 4,
      percent: null,
      distribution: [
        { label: "Disagree", count: 26, percent: 39.4 },
        { label: "Neutral", count: 20, percent: 30.3 },
        { label: "Agree", count: 20, percent: 30.3 },
      ],
    },
  ],
  sentence: "“I worry about my grades” differs by Faculty.",
  warnings: [],
  levels: ["Disagree", "Neutral", "Agree"],
  axis_min: null,
  axis_max: null,
};

describe("formatP", () => {
  it("uses APA style", () => {
    expect(formatP(0.0004)).toBe("p < .001");
    expect(formatP(0.0312)).toBe("p = .031");
  });
});

describe("ComparisonCard", () => {
  it("shows the adjusted p-value, effect size and the reason for the test on demand", () => {
    render(<ComparisonCard comparison={comparison} />);
    expect(screen.getByText("p = .006 (adj.)")).toBeInTheDocument();
    expect(screen.getByText("epsilon² = 0.08 · medium")).toBeInTheDocument();
    expect(screen.queryByText(/compares ranks/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Why this test/ }));
    expect(screen.getByText(/compares ranks/)).toBeInTheDocument();
  });

  it("draws a diverging bar per group, with agree and disagree shares beside it", () => {
    render(<ComparisonCard comparison={comparison} />);
    // Engineering: 57.5% agree (rounded 58%), 19.5% disagree (rounded 20%)
    expect(screen.getByRole("img", { name: /^Engineering: Disagree 20%/ })).toBeInTheDocument();
    expect(screen.getByText("58%")).toBeInTheDocument();
  });

  it("has a table view with the same numbers", () => {
    render(<ComparisonCard comparison={comparison} />);
    fireEvent.click(screen.getByRole("button", { name: "Show table" }));
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("57.5%")).toBeInTheDocument();
  });
});
