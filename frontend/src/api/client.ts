// Typed wrapper around fetch. Every backend call goes through here, so the
// base URL and error handling live in one place.
import type {
  CleaningReport,
  CleaningResult,
  ColumnType,
  EmbeddedColumn,
  Finding,
  TextsToEmbed,
  HealthResponse,
  PrivacyReport,
  StatsReport,
  ThemesReport,
  UploadResponse,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("Can't reach the server. It may be waking up; try again in a minute.", 0);
  }
  if (!response.ok) {
    let detail = response.statusText || "Something went wrong.";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // body was not JSON; keep the status text
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function uploadSurvey(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/api/sessions", { method: "POST", body: form });
}

export function startSampleSession(): Promise<UploadResponse> {
  return request<UploadResponse>("/api/sessions/sample", { method: "POST" });
}

export function confirmColumns(
  sessionId: string,
  types: Record<string, ColumnType>,
): Promise<PrivacyReport> {
  return request<PrivacyReport>(`/api/sessions/${sessionId}/columns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ types }),
  });
}

export function getCleaningReport(sessionId: string): Promise<CleaningReport> {
  return request<CleaningReport>(`/api/sessions/${sessionId}/cleaning`);
}

export function applyCleaning(sessionId: string, apply: string[]): Promise<CleaningResult> {
  return request<CleaningResult>(`/api/sessions/${sessionId}/cleaning`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ apply }),
  });
}

export function getStats(sessionId: string): Promise<StatsReport> {
  return request<StatsReport>(`/api/sessions/${sessionId}/stats`);
}

/** Step 1 of themes: which answers the browser should embed, and with which model. */
export function getTextsToEmbed(sessionId: string): Promise<TextsToEmbed> {
  return request<TextsToEmbed>(`/api/sessions/${sessionId}/texts`);
}

/** Step 2 of themes: send the browser-computed vectors; get labelled themes back. */
export function postThemes(sessionId: string, columns: EmbeddedColumn[]): Promise<ThemesReport> {
  return request<ThemesReport>(`/api/sessions/${sessionId}/themes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ columns }),
  });
}

export function getFindings(sessionId: string): Promise<Finding[]> {
  return request<Finding[]>(`/api/sessions/${sessionId}/findings`);
}

/** The cleaned CSV as a file blob, plus the server's suggested file name. */
export async function downloadCleanedCsv(sessionId: string): Promise<{ blob: Blob; filename: string }> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/sessions/${sessionId}/export/csv`);
  } catch {
    throw new ApiError("Can't reach the server.", 0);
  }
  if (!response.ok) throw new ApiError("The export failed. Please try again.", response.status);
  const header = response.headers.get("Content-Disposition") ?? "";
  const filename = header.match(/filename="([^"]+)"/)?.[1] ?? "survey-cleaned.csv";
  return { blob: await response.blob(), filename };
}

export function deleteSession(sessionId: string): Promise<void> {
  return request<void>(`/api/sessions/${sessionId}`, { method: "DELETE" });
}
