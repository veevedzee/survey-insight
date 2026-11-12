import { describe, expect, it } from "vitest";
import { buildReportHtml, escapeHtml, fileStem, svgColorsToVars } from "./report";

const colors = {
  series1: "#2a78d6",
  grid: "#e6e8f0",
  axis: "#c3c6d4",
  muted: "#5b6178",
  text: "#171b2e",
  surface: "#ffffff",
};

function dashboard(): HTMLElement {
  const root = document.createElement("section");
  root.innerHTML = `
    <nav class="section-nav"><a href="#x">Jump</a></nav>
    <h2>Results</h2>
    <div class="export-bar"><button>Download</button></div>
    <svg><rect fill="#2a78d6"></rect><text style="fill: #5b6178">label</text><path fill="#123456"></path></svg>
    <p class="finding">Stress is highest for Engineering</p>
    <div class="actions"><button>Start over</button></div>`;
  return root;
}

describe("svgColorsToVars", () => {
  it("replaces resolved theme colours with CSS variables and leaves others", () => {
    const root = dashboard();
    svgColorsToVars(root, colors);
    const rect = root.querySelector("rect") as SVGElement;
    expect(rect.getAttribute("fill")).toBeNull();
    expect(rect.style.getPropertyValue("fill")).toBe("var(--series-1)");
    expect((root.querySelector("text") as SVGElement).style.getPropertyValue("fill")).toBe("var(--muted)");
    expect(root.querySelector("path")?.getAttribute("fill")).toBe("#123456");
  });
});

describe("buildReportHtml", () => {
  const html = buildReportHtml(dashboard(), ".x{color:red}", {
    filename: "My <survey>.csv",
    nResponses: 262,
    nExcluded: 38,
    generatedAt: new Date("2026-11-13T10:00:00Z"),
  }, colors);

  it("is a standalone document with the styles inlined", () => {
    expect(html.startsWith("<!doctype html>")).toBe(true);
    expect(html).toContain(".x{color:red}");
    expect(html).toContain("262 responses analysed · 38 excluded");
  });

  it("keeps the results but drops controls that only work in the app", () => {
    expect(html).toContain("Stress is highest for Engineering");
    expect(html).not.toContain("<button");
    expect(html).not.toContain("section-nav");
  });

  it("escapes the file name", () => {
    expect(html).toContain("My &#60;survey&#62;.csv");
    expect(escapeHtml(`"a" & 'b'`)).toBe("&#34;a&#34; &#38; &#39;b&#39;");
  });
});

describe("fileStem", () => {
  it("makes a safe file name stem", () => {
    expect(fileStem("Student Survey (2).xlsx")).toBe("Student_Survey_2");
    expect(fileStem(".csv")).toBe("survey");
  });
});
