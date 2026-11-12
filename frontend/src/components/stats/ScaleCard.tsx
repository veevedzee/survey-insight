import type { ScaleResult } from "../../api/types";
import { formatNumber } from "../../format";

export function ScaleCard({ scale }: { scale: ScaleResult }) {
  return (
    <article className="result-card">
      <header className="result-head">
        <div>
          <h4>{scale.label}</h4>
          <span className="muted small">
            {scale.items.length} items · {scale.n_complete} complete responses
          </span>
        </div>
        <div className="alpha">
          <span className="alpha-value">α = {formatNumber(scale.alpha)}</span>
          <span className={`pill ${scale.reliable ? "pill-ok" : "pill-warn"}`}>
            {scale.interpretation}
          </span>
        </div>
      </header>
      <p className="small muted">
        {scale.reliable
          ? "Reliable enough to combine: the items are averaged into one scale score, which is compared across groups below."
          : "Not reliable enough to combine, so each item is analysed on its own."}
      </p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Item</th>
              <th className="num" title="Correlation with the sum of the other items">
                Item–rest r
              </th>
              <th className="num">α if removed</th>
            </tr>
          </thead>
          <tbody>
            {scale.items.map((item) => (
              <tr key={item.column}>
                <td dir="auto">{item.label}</td>
                <td className="num">{formatNumber(item.item_total_r)}</td>
                <td className="num">{formatNumber(item.alpha_if_deleted)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {scale.warnings.length > 0 && (
        <ul className="warning-list">
          {scale.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </article>
  );
}
