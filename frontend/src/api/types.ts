// Mirrors backend/survey_insight/schemas.py. Keep the two in sync.

export interface HealthResponse {
  status: string;
  version: string;
}

export type ColumnType =
  | "likert"
  | "single_choice"
  | "multiple_choice"
  | "numeric"
  | "text"
  | "timestamp"
  | "identifier"
  | "ignore";

export interface ColumnProfile {
  name: string;
  detected_type: ColumnType;
  reason: string;
  n_missing: number;
  n_unique: number;
  examples: string[];
  scale_group: string | null;
  likert_levels: string[] | null;
}

export interface UploadResponse {
  session_id: string;
  filename: string;
  n_rows: number;
  n_columns: number;
  columns: ColumnProfile[];
}

export interface RemovedColumn {
  name: string;
  n_values: number;
}

export interface MaskedColumn {
  name: string;
  counts: Record<string, number>;
  examples: string[];
}

export interface FlagExample {
  row: number; // 0-based; shown as "response #row+1"
  detail: string;
}

export interface QualityCheck {
  key: string;
  label: string;
  description: string;
  action: "exclude" | "blank";
  available: boolean;
  unavailable_reason: string | null;
  n_flagged: number;
  flagged_rows: number[];
  examples: FlagExample[];
}

export interface Normalization {
  column: string;
  n_changed: number;
  changes: [string, string][];
}

export interface CleaningReport {
  n_rows: number;
  checks: QualityCheck[];
  normalizations: Normalization[];
}

export interface CleaningResult {
  n_before: number;
  n_after: number;
  n_values_blanked: number;
  applied: string[];
}

// ---- Statistics (mirrors the dataclasses in backend/survey_insight/stats.py) ----

export interface ChoiceCount {
  label: string;
  count: number;
  percent: number;
}

export interface HistogramBin {
  start: number;
  end: number;
  count: number;
}

export interface NumericSummary {
  mean: number;
  sd: number;
  median: number;
  q1: number;
  q3: number;
  min: number;
  max: number;
  histogram: HistogramBin[];
  discrete: boolean;
}

export interface LikertSummary {
  median_label: string;
  mean_score: number;
  agree_percent: number;
  disagree_percent: number;
}

export interface QuestionSummary {
  column: string;
  label: string;
  type: ColumnType;
  n: number;
  n_missing: number;
  scale_group: string | null;
  counts: ChoiceCount[] | null;
  numeric: NumericSummary | null;
  likert: LikertSummary | null;
}

export interface ItemStat {
  column: string;
  label: string;
  item_total_r: number | null;
  alpha_if_deleted: number | null;
}

export interface ScaleResult {
  name: string;
  label: string;
  items: ItemStat[];
  n_complete: number;
  alpha: number | null;
  interpretation: string;
  reliable: boolean;
  score_column: string | null;
  warnings: string[];
}

export interface GroupStat {
  group: string;
  n: number;
  median: number | null;
  mean: number | null;
  q1: number | null;
  q3: number | null;
  percent: number | null;
  distribution: ChoiceCount[] | null;
}

export interface Comparison {
  outcome: string;
  outcome_label: string;
  outcome_kind: "likert" | "numeric" | "scale" | "categorical";
  group_by: string;
  test: string;
  test_reason: string;
  statistic: number;
  p_value: number;
  p_adjusted: number;
  significant: boolean;
  effect_name: string;
  effect_size: number;
  effect_label: string;
  n_total: number;
  groups: GroupStat[];
  sentence: string;
  warnings: string[];
  levels: string[] | null;
  axis_min: number | null;
  axis_max: number | null;
}

export interface Correlation {
  x: string;
  y: string;
  x_label: string;
  y_label: string;
  rho: number;
  p_value: number;
  p_adjusted: number;
  significant: boolean;
  effect_label: string;
  n: number;
  sentence: string;
}

export interface StatsReport {
  n_responses: number;
  questions: QuestionSummary[];
  scales: ScaleResult[];
  comparisons: Comparison[];
  correlations: Correlation[];
  notes: string[];
}

// ---- Themes and findings (mirror text_themes.py and findings.py) ----

export interface SentimentSummary {
  n_english: number;
  mean_compound: number;
  positive_percent: number;
  neutral_percent: number;
  negative_percent: number;
}

export interface ThemeQuote {
  text: string;
  language: "en" | "ar" | "mixed";
}

export interface Theme {
  id: number;
  label: string;
  keywords: string[];
  size: number;
  percent: number;
  quotes: ThemeQuote[];
  languages: Record<string, number>;
  sentiment: SentimentSummary | null;
}

export interface ColumnThemes {
  column: string;
  n_answers: number;
  n_used: number;
  n_filler: number;
  sampled: boolean;
  k: number;
  silhouette: number | null;
  quality: string;
  themes: Theme[];
  sentiment: SentimentSummary | null;
  notes: string[];
}

export interface ThemesReport {
  model: string;
  columns: ColumnThemes[];
  sentiment_note: string;
}

export interface TextsToEmbed {
  model: string;
  columns: { column: string; texts: string[] }[];
}

export interface EmbeddedColumn {
  column: string;
  texts: string[];
  vectors: number[][];
}

export interface Finding {
  kind: "difference" | "relationship" | "reliability" | "agreement" | "theme" | "choice" | "quality";
  title: string;
  text: string;
  importance: number;
  evidence: string;
}

export interface PrivacyReport {
  removed_columns: RemovedColumn[];
  masked_columns: MaskedColumn[];
  total_masked: number;
  n_rows: number;
  n_columns: number;
  limitations: string[];
}
