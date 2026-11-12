/// <reference lib="webworker" />
// Runs the multilingual sentence model inside the browser, in a Web Worker so
// the page stays responsive while it works.
//
// Model: Xenova/paraphrase-multilingual-MiniLM-L12-v2, the ONNX conversion of
// the sentence-transformers model we used in Python. "q8" loads the 8-bit
// quantised weights (~120 MB instead of ~470 MB); the browser caches them, so
// only the first visit downloads anything.
import { pipeline, type FeatureExtractionPipeline, type ProgressInfo } from "@huggingface/transformers";
import type { WorkerRequest, WorkerResponse } from "./messages";

const BATCH_SIZE = 32;

let extractor: Promise<FeatureExtractionPipeline> | null = null;

function post(message: WorkerResponse) {
  (self as DedicatedWorkerGlobalScope).postMessage(message);
}

function load(model: string): Promise<FeatureExtractionPipeline> {
  extractor ??= pipeline("feature-extraction", model, {
    dtype: "q8",
    progress_callback: (info: ProgressInfo) => {
      if (info.status === "progress_total") {
        // id 0 = broadcast: the download is shared by every request waiting for it.
        post({ id: 0, type: "progress", stage: "download", done: info.loaded, total: info.total });
      }
    },
  }) as Promise<FeatureExtractionPipeline>;
  return extractor;
}

self.onmessage = async (event: MessageEvent<WorkerRequest>) => {
  const { id, model, texts } = event.data;
  try {
    const embed = await load(model);
    const vectors: number[][] = [];
    for (let start = 0; start < texts.length; start += BATCH_SIZE) {
      const batch = texts.slice(start, start + BATCH_SIZE);
      // Mean pooling + L2 normalisation: the same recipe sentence-transformers uses.
      const output = await embed(batch, { pooling: "mean", normalize: true });
      for (const row of output.tolist() as number[][]) {
        // 4 decimals is plenty for clustering and keeps the upload small.
        vectors.push(row.map((v) => Math.round(v * 1e4) / 1e4));
      }
      post({ id, type: "progress", stage: "embed", done: vectors.length, total: texts.length });
    }
    post({ id, type: "result", vectors });
  } catch (error) {
    extractor = null; // allow a retry, e.g. after a network hiccup during download
    post({ id, type: "error", message: error instanceof Error ? error.message : String(error) });
  }
};
