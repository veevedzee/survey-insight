// Messages between the page and the embedding worker.

export interface WorkerRequest {
  id: number;
  model: string;
  texts: string[];
}

export type EmbedProgress =
  /** Model files downloading (bytes). Only on the first visit; later it comes from the cache. */
  | { stage: "download"; done: number; total: number }
  /** Answers turned into vectors so far. */
  | { stage: "embed"; done: number; total: number };

export type WorkerResponse =
  | ({ id: number; type: "progress" } & EmbedProgress)
  | { id: number; type: "result"; vectors: number[][] }
  | { id: number; type: "error"; message: string };
