/// <reference lib="webworker" />
// Runs the Python analysis package inside the browser with Pyodide (CPython
// compiled to WebAssembly). This is what makes the hosted demo serverless:
// uploads, privacy masking, cleaning, statistics and themes all run here, on
// the visitor's device, in a background thread so the page stays responsive.
import type { EngineRequest, EngineResponse } from "./messages";

// Pinned for reproducibility: Python 3.14, pandas 3.0, SciPy 1.18, scikit-learn 1.8.
const PYODIDE_VERSION = "314.0.7";
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const APP_DIR = "/home/pyodide/app";

interface PyodideAPI {
  loadPackage(names: string[], options?: { messageCallback?: (msg: string) => void }): Promise<void>;
  pyimport(name: string): any;
  runPythonAsync(code: string): Promise<unknown>;
  FS: { mkdirTree(path: string): void; writeFile(path: string, data: string | Uint8Array): void };
}

let ready: Promise<{ bridge: any }> | null = null;

function post(message: EngineResponse) {
  (self as DedicatedWorkerGlobalScope).postMessage(message);
}

function status(stage: "loading" | "ready", message: string, progress: number | null) {
  post({ id: 0, kind: "status", stage, message, progress });
}

async function boot(): Promise<{ bridge: any }> {
  status("loading", "Starting Python in your browser…", 0.05);
  const { loadPyodide } = await import(/* @vite-ignore */ `${PYODIDE_URL}pyodide.mjs`);
  const pyodide: PyodideAPI = await loadPyodide({ indexURL: PYODIDE_URL });

  status("loading", "Loading pandas, SciPy and scikit-learn…", 0.3);
  await pyodide.loadPackage(["numpy", "pandas", "scipy", "scikit-learn", "micropip"]);

  status("loading", "Installing the remaining packages…", 0.75);
  // Pure-Python packages not bundled with Pyodide, installed from PyPI.
  const micropip = pyodide.pyimport("micropip");
  await micropip.install(["openpyxl==3.1.5", "vaderSentiment==3.3.2"]);

  status("loading", "Loading the analysis code…", 0.9);
  const base = new URL(`${import.meta.env.BASE_URL}py/`, self.location.origin);
  const manifest = (await (await fetch(new URL("manifest.json", base))).json()) as {
    package: string[];
    sample: string;
  };
  pyodide.FS.mkdirTree(`${APP_DIR}/backend/survey_insight`);
  pyodide.FS.mkdirTree(`${APP_DIR}/sample_data`);
  await Promise.all(
    manifest.package.map(async (file) => {
      const text = await (await fetch(new URL(file, base))).text();
      pyodide.FS.writeFile(`${APP_DIR}/backend/${file}`, text);
    }),
  );
  const sample = new Uint8Array(await (await fetch(new URL(manifest.sample, base))).arrayBuffer());
  pyodide.FS.writeFile(`${APP_DIR}/sample_data/${manifest.sample}`, sample);

  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "${APP_DIR}/backend")
`);
  const bridge = pyodide.pyimport("survey_insight.bridge");
  status("ready", "Ready: everything runs on your device", 1);
  return { bridge };
}

function engine() {
  ready ??= boot().catch((error) => {
    ready = null; // allow a retry
    throw error;
  });
  return ready;
}

self.onmessage = async (event: MessageEvent<EngineRequest>) => {
  const request = event.data;
  try {
    const { bridge } = await engine();
    if (request.kind === "start") return;
    let raw: string;
    if (request.kind === "upload") {
      raw = bridge.upload_js(request.filename, new Uint8Array(request.data));
    } else {
      raw = bridge.handle(request.method, request.path, request.body ?? null);
    }
    const { status: code, body } = JSON.parse(raw);
    post({ id: request.id, kind: "response", status: code, body });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (ready === null) {
      // Python itself failed to load (e.g. no internet on the first visit).
      post({ id: 0, kind: "status", stage: "error", message: `Couldn't start Python: ${message}`, progress: null });
    }
    if (request.kind !== "start") post({ id: request.id, kind: "failure", message });
  }
};
