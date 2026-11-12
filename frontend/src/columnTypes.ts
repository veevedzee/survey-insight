// Display information for each column type, shared by every screen.
import type { ColumnType } from "./api/types";

export const COLUMN_TYPES: Record<ColumnType, { label: string; hint: string }> = {
  likert: { label: "Likert scale", hint: "Ordered agreement/rating answers" },
  single_choice: { label: "Single choice", hint: "One option per person" },
  multiple_choice: { label: "Multiple choice", hint: "Several options, comma-separated" },
  numeric: { label: "Numeric", hint: "Numbers such as age or hours" },
  text: { label: "Free text", hint: "Open-ended written answers" },
  timestamp: { label: "Timestamp", hint: "Dates and times" },
  identifier: { label: "Personal data", hint: "Removed before analysis" },
  ignore: { label: "Ignore", hint: "Left out of the analysis" },
};

export const TYPE_ORDER: ColumnType[] = [
  "likert",
  "single_choice",
  "multiple_choice",
  "numeric",
  "text",
  "timestamp",
  "identifier",
  "ignore",
];

/** For a grid column "Question [item]", return the item text; otherwise the full name. */
export function shortColumnName(name: string, scaleGroup: string | null): string {
  if (!scaleGroup) return name;
  const match = name.match(/\[([^\]]+)\]\s*$/);
  return match ? match[1] : name;
}
