// Chart colours come from CSS variables (styles.css) so light/dark mode swap in
// one place. HTML charts use the variables directly; Recharts (SVG attributes)
// gets resolved hex values through useChartColors().
import { useEffect, useState } from "react";

const CATEGORICAL = ["--cat-1", "--cat-2", "--cat-3", "--cat-4", "--cat-5", "--cat-6", "--cat-7", "--cat-8"];
export const MAX_CATEGORIES = CATEGORICAL.length;

/** Categorical slot for the i-th category, in fixed order (never cycled). */
export function categoricalVar(i: number): string {
  return `var(${CATEGORICAL[Math.min(i, CATEGORICAL.length - 1)]})`;
}

/** Text colour that stays readable inside a categorical fill (dark ink on yellow). */
export function inkOnCategorical(i: number): string {
  return i === 3 ? "#0b0b0b" : "#ffffff";
}

/**
 * Colours for a diverging Likert scale with k levels: red arm (disagree),
 * grey midpoint when k is odd, blue arm (agree). Outer levels are the
 * strongest; inner steps are mixed between the two validated endpoints.
 */
export function divergingColors(k: number): string[] {
  const arm = Math.floor(k / 2);
  const step = (strong: string, light: string, i: number) => {
    if (arm === 1) return `var(${strong})`;
    const t = i / (arm - 1); // 0 = outermost (strong) ... 1 = innermost (light)
    if (t === 0) return `var(${strong})`;
    if (t === 1) return `var(${light})`;
    return `color-mix(in oklab, var(${strong}) ${Math.round((1 - t) * 100)}%, var(${light}))`;
  };
  const negative = Array.from({ length: arm }, (_, i) => step("--div-neg-2", "--div-neg-1", i));
  const positive = Array.from({ length: arm }, (_, i) => step("--div-pos-2", "--div-pos-1", i)).reverse();
  return k % 2 === 1 ? [...negative, "var(--div-mid)", ...positive] : [...negative, ...positive];
}

export interface ChartColors {
  series1: string;
  grid: string;
  axis: string;
  muted: string;
  text: string;
  surface: string;
}

function readColors(): ChartColors {
  const css = getComputedStyle(document.documentElement);
  const get = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return {
    series1: get("--series-1", "#2a78d6"),
    grid: get("--chart-grid", "#e6e8f0"),
    axis: get("--chart-axis", "#c3c6d4"),
    muted: get("--muted", "#5b6178"),
    text: get("--text", "#171b2e"),
    surface: get("--surface", "#ffffff"),
  };
}

/** Resolved chart colours that update when the OS switches light/dark mode. */
export function useChartColors(): ChartColors {
  const [colors, setColors] = useState<ChartColors>(readColors);
  useEffect(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    const update = () => setColors(readColors());
    query?.addEventListener?.("change", update);
    return () => query?.removeEventListener?.("change", update);
  }, []);
  return colors;
}
