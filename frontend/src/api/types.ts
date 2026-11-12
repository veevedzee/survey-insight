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

export interface PrivacyReport {
  removed_columns: RemovedColumn[];
  masked_columns: MaskedColumn[];
  total_masked: number;
  n_rows: number;
  n_columns: number;
  limitations: string[];
}
