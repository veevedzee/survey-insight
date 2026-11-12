import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CleaningReport, QualityCheck } from "../api/types";
import { CleaningStep, excludedRows } from "./CleaningStep";

function check(key: string, rows: number[], action: "exclude" | "blank" = "exclude"): QualityCheck {
  return {
    key,
    label: key,
    description: "",
    action,
    available: true,
    unavailable_reason: null,
    n_flagged: rows.length,
    flagged_rows: rows,
    examples: rows.map((row) => ({ row, detail: `flagged ${row}` })),
  };
}

const report: CleaningReport = {
  n_rows: 10,
  checks: [check("duplicates", [1, 2]), check("speeders", [2, 3]), check("outliers", [4], "blank")],
  normalizations: [],
};

describe("excludedRows", () => {
  it("counts a response flagged twice only once, and ignores 'blank' checks", () => {
    const rows = excludedRows(report.checks, new Set(["duplicates", "speeders", "outliers"]));
    expect([...rows].sort()).toEqual([1, 2, 3]);
  });
});

describe("CleaningStep", () => {
  it("updates the kept count when a check is unticked and sends the choice", () => {
    const onApply = vi.fn();
    render(<CleaningStep report={report} busy={false} onApply={onApply} onBack={() => {}} />);

    expect(screen.getByText("7")).toBeInTheDocument(); // 10 - {1,2,3}
    fireEvent.click(screen.getByLabelText("Exclude these responses: speeders"));
    expect(screen.getByText("8")).toBeInTheDocument(); // 10 - {1,2}

    fireEvent.click(screen.getByRole("button", { name: "Apply and continue" }));
    expect(onApply).toHaveBeenCalledWith(["duplicates", "outliers"]);
  });
});
