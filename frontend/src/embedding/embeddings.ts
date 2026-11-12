// Page-side helper: send answers to the worker and get their vectors back.
import type { EmbedProgress, WorkerRequest, WorkerResponse } from "./messages";

export type { EmbedProgress };

let worker: Worker | null = null;
let nextId = 1;

function getWorker(): Worker {
  // Created on first use, so visitors who never reach the themes don't pay for it.
  worker ??= new Worker(new URL("./embeddingWorker.ts", import.meta.url), { type: "module" });
  return worker;
}

/** Turn texts into vectors in the browser (one 384-number vector per text). */
export function embedTexts(
  model: string,
  texts: string[],
  onProgress: (progress: EmbedProgress) => void,
): Promise<number[][]> {
  if (texts.length === 0) return Promise.resolve([]);
  const w = getWorker();
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      w.removeEventListener("message", onMessage);
      w.removeEventListener("error", onError);
    };
    const onMessage = (event: MessageEvent<WorkerResponse>) => {
      const msg = event.data;
      // id 0 is the shared model download, relevant to every waiting request.
      if (msg.id !== id && msg.id !== 0) return;
      if (msg.type === "progress") {
        onProgress(msg.stage === "download"
          ? { stage: "download", done: msg.done, total: msg.total }
          : { stage: "embed", done: msg.done, total: msg.total });
        return;
      }
      cleanup();
      if (msg.type === "result") resolve(msg.vectors);
      else reject(new Error(msg.message));
    };
    // The worker script itself failed (e.g. it couldn't be loaded): fail loudly
    // instead of waiting forever, and start a fresh worker next time.
    const onError = (event: ErrorEvent) => {
      cleanup();
      worker?.terminate();
      worker = null;
      reject(new Error(event.message || "The language model worker crashed."));
    };
    w.addEventListener("message", onMessage);
    w.addEventListener("error", onError);
    const request: WorkerRequest = { id, model, texts };
    w.postMessage(request);
  });
}

/** Human-readable status for the progress line. */
export function describeProgress(p: EmbedProgress | null): string {
  if (!p) return "Loading the language model in your browser…";
  if (p.stage === "download") {
    if (p.total && p.done >= p.total) return "Starting the language model…";
    const mb = (bytes: number) => Math.round(bytes / 1e6);
    const pct = p.total ? Math.round((100 * p.done) / p.total) : 0;
    return `Downloading the language model to your browser: ${mb(p.done)} of ${mb(p.total)} MB (${pct}%). This happens only once.`;
  }
  return `Reading answers on your device: ${p.done} of ${p.total}`;
}
