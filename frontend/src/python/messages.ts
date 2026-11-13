// Messages between the page and the Python worker.

export type EngineRequest =
  | { id: number; kind: "start" }
  | { id: number; kind: "call"; method: string; path: string; body?: string }
  | { id: number; kind: "upload"; filename: string; data: ArrayBuffer };

export type EngineStage = "idle" | "loading" | "ready" | "error";

export type EngineResponse =
  | { id: 0; kind: "status"; stage: EngineStage; message: string; progress: number | null }
  | { id: number; kind: "response"; status: number; body: unknown }
  | { id: number; kind: "failure"; message: string };
