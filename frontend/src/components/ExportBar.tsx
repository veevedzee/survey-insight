import { useState, type RefObject } from "react";
import { ApiError, downloadCleanedCsv } from "../api/client";
import { buildReportHtml, collectCss, fileStem, saveFile } from "../report";
import { useChartColors } from "./charts/palette";

interface Props {
  sessionId: string;
  filename: string;
  nResponses: number;
  nExcluded: number;
  dashboardRef: RefObject<HTMLElement | null>;
  /** Themes still loading: the report would be missing them. */
  reportReady: boolean;
}

export function ExportBar({ sessionId, filename, nResponses, nExcluded, dashboardRef, reportReady }: Props) {
  const colors = useChartColors();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function exportCsv() {
    setBusy(true);
    setError(null);
    try {
      const { blob, filename: name } = await downloadCleanedCsv(sessionId);
      saveFile(blob, name);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The export failed.");
    } finally {
      setBusy(false);
    }
  }

  function exportReport() {
    if (!dashboardRef.current) return;
    const html = buildReportHtml(
      dashboardRef.current,
      collectCss(),
      { filename, nResponses, nExcluded, generatedAt: new Date() },
      colors,
    );
    saveFile(html, `${fileStem(filename)}-report.html`);
  }

  return (
    <div className="export-bar">
      <button type="button" className="button button-secondary" onClick={exportCsv} disabled={busy}>
        {busy ? "Preparing…" : "Download cleaned CSV"}
      </button>
      <button
        type="button"
        className="button"
        onClick={exportReport}
        disabled={!reportReady}
        title={reportReady ? "A single HTML file: open it offline or print it to PDF" : "Waiting for the themes to finish"}
      >
        Download HTML report
      </button>
      {error && <span className="error-text small">{error}</span>}
    </div>
  );
}
