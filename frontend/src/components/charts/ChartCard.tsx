import { useState, type ReactNode } from "react";

interface Props {
  title: string;
  meta?: string;
  children: ReactNode;
  /** The same data as a table: the accessible twin of every chart. */
  table: ReactNode;
  wide?: boolean;
}

export function ChartCard({ title, meta, children, table, wide }: Props) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure className={`chart-card${wide ? " chart-card-wide" : ""}`}>
      <figcaption className="chart-head">
        <div>
          <h4 dir="auto">{title}</h4>
          {meta && <span className="muted small">{meta}</span>}
        </div>
        <button
          type="button"
          className="link-button flush nowrap"
          onClick={() => setShowTable((s) => !s)}
          aria-pressed={showTable}
        >
          {showTable ? "Show chart" : "Show table"}
        </button>
      </figcaption>
      {showTable ? <div className="table-wrap">{table}</div> : children}
    </figure>
  );
}
