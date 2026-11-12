// Number formatting shared by the statistics views.

/** APA style: no leading zero, "< .001" for tiny values. */
export function formatP(p: number): string {
  if (p < 0.001) return "p < .001";
  return `p = ${p.toFixed(3).replace(/^0\./, ".")}`;
}

export function formatNumber(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  return Number.isInteger(x) ? String(x) : x.toFixed(digits);
}
