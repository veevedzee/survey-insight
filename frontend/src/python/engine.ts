// Page-side handle on the in-browser Python engine (see pythonWorker.ts).
import { useEffect, useState } from "react";
import type { EngineRequest, EngineResponse, EngineStage } from "./messages";

export interface EngineStatus {
  stage: EngineStage;
  message: string;
  /** 0..1 while loading, null when unknown. */
  progress: number | null;
}

export interface EngineReply {
  status: number;
  body: unknown;
}

let worker: Worker | null = null;
let nextId = 1;
let current: EngineStatus = { stage: "idle", message: "Not started", progress: null };
const statusListeners = new Set<(s: EngineStatus) => void>();
const pending = new Map<number, { resolve: (r: EngineReply) => void; reject: (e: Error) => void }>();

function setStatus(status: EngineStatus) {
  current = status;
  statusListeners.forEach((listener) => listener(status));
}

function getWorker(): Worker {
  if (worker) return worker;
  worker = new Worker(new URL("./pythonWorker.ts", import.meta.url), { type: "module" });
  worker.addEventListener("message", (event: MessageEvent<EngineResponse>) => {
    const msg = event.data;
    if (msg.kind === "status") {
      setStatus({ stage: msg.stage, message: msg.message, progress: msg.progress });
      return;
    }
    const waiting = pending.get(msg.id);
    if (!waiting) return;
    pending.delete(msg.id);
    if (msg.kind === "response") waiting.resolve({ status: msg.status, body: msg.body });
    else {
      setStatus({ stage: "error", message: msg.message, progress: null });
      waiting.reject(new Error(msg.message));
    }
  });
  worker.addEventListener("error", (event) => {
    const message = event.message || "The Python engine crashed.";
    setStatus({ stage: "error", message, progress: null });
    pending.forEach(({ reject }) => reject(new Error(message)));
    pending.clear();
    worker?.terminate();
    worker = null;
  });
  return worker;
}

// Omit "id" from each member of the union (plain Omit would merge them).
type WithoutId<T> = T extends unknown ? Omit<T, "id"> : never;

function send(request: WithoutId<EngineRequest>, transfer: Transferable[] = []): Promise<EngineReply> {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    getWorker().postMessage({ ...request, id } as EngineRequest, transfer);
  });
}

/** Start downloading Python and the libraries in the background (safe to call twice). */
export function startEngine(): void {
  if (typeof Worker === "undefined") {
    setStatus({ stage: "error", message: "This browser doesn't support Web Workers.", progress: null });
    return;
  }
  if (current.stage === "idle" || current.stage === "error") {
    setStatus({ stage: "loading", message: "Starting Python in your browser…", progress: 0 });
    getWorker().postMessage({ id: 0, kind: "start" } satisfies EngineRequest);
  }
}

/** Call an API route on the in-browser engine; same paths as the HTTP API. */
export function callEngine(method: string, path: string, body?: string): Promise<EngineReply> {
  startEngine();
  return send({ kind: "call", method, path, body });
}

/** Analyse a file without it ever leaving this device. */
export async function uploadToEngine(file: File): Promise<EngineReply> {
  startEngine();
  const data = await file.arrayBuffer();
  return send({ kind: "upload", filename: file.name, data }, [data]);
}

export function getEngineStatus(): EngineStatus {
  return current;
}

/** React hook: live engine status for progress messages and badges. */
export function useEngineStatus(): EngineStatus {
  const [status, setLocal] = useState(current);
  useEffect(() => {
    statusListeners.add(setLocal);
    setLocal(current);
    return () => {
      statusListeners.delete(setLocal);
    };
  }, []);
  return status;
}
