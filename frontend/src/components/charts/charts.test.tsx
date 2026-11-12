import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { sortChoices } from "./ChoiceBarChart";
import { LikertChart } from "./LikertChart";
import { divergingColors } from "./palette";
import { niceTicks } from "./RangeChart";

describe("divergingColors", () => {
  it("puts grey in the middle of an odd scale and keeps the arms symmetric", () => {
    const five = divergingColors(5);
    expect(five).toHaveLength(5);
    expect(five[2]).toBe("var(--div-mid)");
    expect(five[0]).toBe("var(--div-neg-2)");
    expect(five[4]).toBe("var(--div-pos-2)");
  });

  it("has no midpoint for an even scale", () => {
    expect(divergingColors(4)).not.toContain("var(--div-mid)");
  });
});

describe("sortChoices", () => {
  const c = (label: string, count: number) => ({ label, count, percent: count });
  it("keeps ordered categories in their natural order", () => {
    const sorted = sortChoices([c("2nd year", 9), c("1st year", 5), c("10th year", 1)]);
    expect(sorted.map((x) => x.label)).toEqual(["1st year", "2nd year", "10th year"]);
  });
  it("sorts plain categories by frequency", () => {
    const sorted = sortChoices([c("Business", 3), c("Engineering", 9)]);
    expect(sorted.map((x) => x.label)).toEqual(["Engineering", "Business"]);
  });
});

describe("niceTicks", () => {
  it("chooses round steps", () => {
    expect(niceTicks(1, 5)).toEqual([1, 2, 3, 4, 5]);
    expect(niceTicks(0, 10)).toEqual([0, 2.5, 5, 7.5, 10]);
  });
});

describe("LikertChart", () => {
  it("centres the neutral share on the zero line", () => {
    const levels = ["Disagree", "Neutral", "Agree"];
    render(
      <LikertChart
        levels={levels}
        rows={[
          {
            key: "q",
            label: "Q",
            counts: [
              { label: "Disagree", count: 20, percent: 20 },
              { label: "Neutral", count: 40, percent: 40 },
              { label: "Agree", count: 40, percent: 40 },
            ],
          },
        ]}
      />,
    );
    const neutral = screen.getByTitle("Neutral: 40% (40)") as HTMLElement;
    // Track spans -100..100 so neutral 40% is 20% wide, centred: 40%..60%.
    expect(neutral.style.left).toBe("40%");
    expect(neutral.style.width).toBe("20%");
  });
});
