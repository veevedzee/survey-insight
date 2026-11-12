// Builds a self-contained HTML report from the rendered dashboard.
//
// Why snapshot the page instead of generating the report on the server?
// The dashboard *is* the report: re-drawing every chart in Python would mean
// two implementations of each chart that drift apart. A snapshot is exactly
// what the user saw, in one file that opens offline, prints to PDF, and
// contains no data beyond the (already anonymised) results.
import type { ChartColors } from "./components/charts/palette";

export interface ReportMeta {
  filename: string;
  nResponses: number;
  nExcluded: number;
  generatedAt: Date;
}

/** Elements that only make sense in the live app. */
const INTERACTIVE = [".section-nav", ".actions", ".export-bar", ".card-links", "button", "input", ".toggle"];

const CSS_VARIABLE_FOR: Record<keyof ChartColors, string> = {
  series1: "--series-1",
  grid: "--chart-grid",
  axis: "--chart-axis",
  muted: "--muted",
  text: "--text",
  surface: "--surface",
};

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

function hexToRgb(hex: string): string | null {
  const m = hex.trim().match(/^#([0-9a-f]{6})$/i);
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}

/**
 * Recharts writes resolved colours (e.g. fill="#3987e5") into the SVG. Swap
 * them back to CSS variables so the saved report follows the reader's light
 * or dark mode instead of freezing the mode it was exported in.
 */
export function svgColorsToVars(root: Element, colors: ChartColors): void {
  const lookup = new Map<string, string>();
  for (const [key, cssVar] of Object.entries(CSS_VARIABLE_FOR)) {
    const value = colors[key as keyof ChartColors].trim().toLowerCase();
    lookup.set(value, cssVar);
    const rgb = hexToRgb(value);
    if (rgb) lookup.set(rgb, cssVar);
  }
  root.querySelectorAll<SVGElement>("svg, svg *").forEach((el) => {
    for (const prop of ["fill", "stroke"] as const) {
      const attr = el.getAttribute(prop)?.trim().toLowerCase();
      if (attr && lookup.has(attr)) {
        el.removeAttribute(prop);
        el.style.setProperty(prop, `var(${lookup.get(attr)})`);
      }
      const inline = el.style.getPropertyValue(prop).trim().toLowerCase();
      if (inline && lookup.has(inline)) {
        el.style.setProperty(prop, `var(${lookup.get(inline)})`);
      }
    }
  });
}

/** All same-origin CSS rules on the page (cross-origin font sheets are linked instead). */
export function collectCss(): string {
  const parts: string[] = [];
  for (const sheet of Array.from(document.styleSheets)) {
    try {
      parts.push(Array.from(sheet.cssRules, (r) => r.cssText).join("\n"));
    } catch {
      // Cross-origin stylesheet (Google Fonts): can't be read, and is linked below.
    }
  }
  return parts.join("\n");
}

const REPORT_CSS = `
.report-head { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
  align-items: flex-end; margin-bottom: 1.5rem; }
.report-head h1 { font-size: 1.6rem; margin: 0; }
.report-meta { color: var(--muted); font-size: 0.85rem; text-align: right; }
.report-note { font-size: 0.8rem; color: var(--muted); margin-top: 2rem; text-align: center; }
@media print {
  body { background: #fff !important; }
  .card, .chart-card, .result-card, .theme-card, .finding { box-shadow: none !important; }
  .chart-card, .result-card, .theme-card, .finding, .stat { break-inside: avoid; }
  .section-title { break-after: avoid; }
}
`;

export function buildReportHtml(dashboard: HTMLElement, css: string, meta: ReportMeta,
  colors: ChartColors): string {
  const clone = dashboard.cloneNode(true) as HTMLElement;
  clone.querySelectorAll(INTERACTIVE.join(",")).forEach((el) => el.remove());
  svgColorsToVars(clone, colors);

  const title = `Survey Insight report: ${meta.filename}`;
  const date = meta.generatedAt.toLocaleString("en-GB", { dateStyle: "long", timeStyle: "short" });
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
${css}
${REPORT_CSS}
</style>
</head>
<body>
<div class="app report">
  <header class="report-head">
    <div>
      <h1>Survey Insight report</h1>
      <div class="muted">${escapeHtml(meta.filename)}</div>
    </div>
    <div class="report-meta">
      ${meta.nResponses} responses analysed · ${meta.nExcluded} excluded during cleaning<br>
      Generated ${escapeHtml(date)}
    </div>
  </header>
  <main class="card card-main">
${clone.outerHTML}
  </main>
  <p class="report-note">Created with Survey Insight, an open-source survey analytics tool.
  Personal data was removed before analysis. Statistics use Holm-adjusted p-values; themes
  come from an open-source multilingual model; sentiment covers English answers only.</p>
</div>
</body>
</html>`;
}

/** Save text or a blob as a file through a temporary link. */
export function saveFile(content: Blob | string, filename: string, type = "text/html"): void {
  const blob = typeof content === "string" ? new Blob([content], { type: `${type};charset=utf-8` }) : content;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** "Student Survey (2).xlsx" -> "Student_Survey_2" */
export function fileStem(filename: string): string {
  const stem = filename.replace(/\.[^.]+$/, "").replace(/[^\w-]+/g, "_").replace(/^_+|_+$/g, "");
  return stem || "survey";
}
