import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { UploadResponse } from "../api/types";
import { ColumnsStep } from "./ColumnsStep";

const upload: UploadResponse = {
  session_id: "abc",
  filename: "survey.csv",
  n_rows: 10,
  n_columns: 2,
  columns: [
    {
      name: "Age",
      detected_type: "numeric",
      reason: "Answers are numbers.",
      n_missing: 1,
      n_unique: 5,
      examples: ["19", "20"],
      scale_group: null,
      likert_levels: null,
    },
    {
      name: "Email",
      detected_type: "identifier",
      reason: "The header looks like a personal-data field.",
      n_missing: 0,
      n_unique: 10,
      examples: ["a••••m"],
      scale_group: null,
      likert_levels: null,
    },
  ],
};

describe("ColumnsStep", () => {
  it("sends the corrected types when confirmed", () => {
    const onConfirm = vi.fn();
    render(<ColumnsStep upload={upload} busy={false} onConfirm={onConfirm} onBack={() => {}} />);

    fireEvent.change(screen.getByLabelText("Type of Age"), { target: { value: "single_choice" } });
    expect(screen.getByText(/1 type changed/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Confirm and remove personal data/ }));
    expect(onConfirm).toHaveBeenCalledWith({ Age: "single_choice", Email: "identifier" });
  });

  it("tells the user how many personal-data columns will be removed", () => {
    render(<ColumnsStep upload={upload} busy={false} onConfirm={() => {}} onBack={() => {}} />);
    expect(screen.getByText(/1 personal-data column will be/)).toBeInTheDocument();
  });
});
