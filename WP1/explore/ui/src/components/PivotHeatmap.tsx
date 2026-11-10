import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  useCurrentRefinements,
  useInstantSearch,
  useSearchBox,
} from "react-instantsearch";
import { refinementsToFilterBy } from "./filters";

export const PIVOT_FIELDS: { value: string; label: string }[] = [
  { value: "source", label: "Source" },
  { value: "organism", label: "Organism" },
  { value: "top_organ", label: "Top organ" },
  { value: "tissue", label: "Tissue" },
  { value: "tissue_type", label: "Tissue type" },
  { value: "assay", label: "Assay" },
  { value: "disease", label: "Disease" },
  { value: "cell_type", label: "Cell type" },
  { value: "development_stage", label: "Development stage" },
  { value: "suspension_type", label: "Suspension" },
  { value: "sex", label: "Sex" },
  { value: "study_journal", label: "Journal" },
];

type PivotResponse = {
  row_field: string;
  col_field: string;
  rows: string[];
  cols: string[];
  matrix: number[][];
  row_totals: number[];
  col_totals: number[];
  max_cell: number;
  found: number;
  docs_scanned: number;
  truncated_rows: number;
  truncated_cols: number;
  q: string;
  filter_by: string | null;
};

const STORAGE_KEY = "fenix-explore-pivot-axes";
const NONE_LABEL = "(none)";

function loadAxes(): { row: string; col: string } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as { row?: string; col?: string };
      if (
        parsed.row &&
        parsed.col &&
        parsed.row !== parsed.col &&
        PIVOT_FIELDS.some((f) => f.value === parsed.row) &&
        PIVOT_FIELDS.some((f) => f.value === parsed.col)
      ) {
        return { row: parsed.row, col: parsed.col };
      }
    }
  } catch {
    // ignore
  }
  return { row: "organism", col: "top_organ" };
}

function cellStyle(count: number, max: number): CSSProperties {
  if (!count || max <= 0) {
    return { background: "rgba(255,255,255,0.55)", color: "var(--muted)" };
  }
  const t = Math.sqrt(count / max);
  const alpha = 0.18 + t * 0.72;
  return {
    background: `rgba(15, 106, 92, ${alpha.toFixed(3)})`,
    color: t > 0.55 ? "#f4fffb" : "var(--ink)",
    fontWeight: t > 0.35 ? 600 : 500,
  };
}

type Props = {
  /** Switch the main results pane to a hits view after applying cell filters. */
  onOpenHits: () => void;
};

export function PivotHeatmap({ onOpenHits }: Props) {
  const { query } = useSearchBox();
  const { setIndexUiState } = useInstantSearch();
  const { items: refinementItems } = useCurrentRefinements();
  const filterBy = useMemo(
    () => refinementsToFilterBy(refinementItems),
    [refinementItems]
  );

  const [axes, setAxes] = useState(loadAxes);
  const [data, setData] = useState<PivotResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(axes));
    } catch {
      // ignore
    }
  }, [axes]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const timer = window.setTimeout(() => {
      fetch("/api/pivot", {
        method: "POST",
        headers: { "content-type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          row_field: axes.row,
          col_field: axes.col,
          q: query?.trim() ? query.trim() : "*",
          filter_by: filterBy,
          max_rows: 18,
          max_cols: 18,
        }),
      })
        .then(async (response) => {
          if (!response.ok) {
            const detail = await response.text();
            throw new Error(detail || `Pivot failed (${response.status})`);
          }
          return response.json() as Promise<PivotResponse>;
        })
        .then((payload) => {
          setData(payload);
          setLoading(false);
        })
        .catch((err: Error) => {
          if (err.name === "AbortError") return;
          setError(err.message);
          setLoading(false);
        });
    }, 180);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [axes.row, axes.col, query, filterBy]);

  const swapAxes = () => {
    setAxes((prev) => ({ row: prev.col, col: prev.row }));
  };

  const drillIntoCell = (rowValue: string, colValue: string, count: number) => {
    if (!count) return;

    setIndexUiState((previous) => {
      const refinementList = { ...(previous.refinementList ?? {}) };

      if (rowValue && rowValue !== NONE_LABEL) {
        refinementList[axes.row] = [rowValue];
      }
      if (colValue && colValue !== NONE_LABEL) {
        refinementList[axes.col] = [colValue];
      }

      return {
        ...previous,
        page: 1,
        refinementList,
      };
    });

    onOpenHits();
  };

  return (
    <div className="pivot-panel">
      <div className="pivot-toolbar">
        <label className="group-by-control">
          <span className="group-by-label">Rows</span>
          <select
            value={axes.row}
            onChange={(event) => {
              const next = event.target.value;
              setAxes((prev) =>
                next === prev.col
                  ? { row: next, col: prev.row }
                  : { ...prev, row: next }
              );
            }}
          >
            {PIVOT_FIELDS.map((field) => (
              <option key={field.value} value={field.value}>
                {field.label}
              </option>
            ))}
          </select>
        </label>

        <button type="button" className="pivot-swap" onClick={swapAxes} title="Swap axes">
          ⇄
        </button>

        <label className="group-by-control">
          <span className="group-by-label">Columns</span>
          <select
            value={axes.col}
            onChange={(event) => {
              const next = event.target.value;
              setAxes((prev) =>
                next === prev.row
                  ? { row: prev.col, col: next }
                  : { ...prev, col: next }
              );
            }}
          >
            {PIVOT_FIELDS.map((field) => (
              <option key={field.value} value={field.value}>
                {field.label}
              </option>
            ))}
          </select>
        </label>

        <p className="group-by-hint">
          Cells = dataset counts. Click a cell to filter InstantSearch and open
          the hits view.
        </p>
      </div>

      {loading && !data ? <p className="empty-results">Building pivot…</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {data ? (
        <>
          <div className="pivot-meta">
            <span>
              {data.found.toLocaleString()} matching experiments
              {loading ? " · updating…" : ""}
            </span>
            {filterBy ? <span className="pivot-filter">Filtered</span> : null}
            {data.truncated_rows || data.truncated_cols ? (
              <span>
                Showing top {data.rows.length}×{data.cols.length}
                {data.truncated_rows ? ` (+${data.truncated_rows} rows)` : ""}
                {data.truncated_cols ? ` (+${data.truncated_cols} cols)` : ""}
              </span>
            ) : null}
          </div>

          <div className="pivot-scroll">
            <table className="pivot-table">
              <thead>
                <tr>
                  <th className="pivot-corner">
                    {labelFor(axes.row)} × {labelFor(axes.col)}
                  </th>
                  {data.cols.map((col, index) => (
                    <th key={col} title={`${col} · ${data.col_totals[index]} total`}>
                      <span>{col}</span>
                      <em>{data.col_totals[index]}</em>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, rowIndex) => (
                  <tr key={row}>
                    <th scope="row" title={`${row} · ${data.row_totals[rowIndex]} total`}>
                      <span>{row}</span>
                      <em>{data.row_totals[rowIndex]}</em>
                    </th>
                    {data.cols.map((col, colIndex) => {
                      const count = data.matrix[rowIndex]?.[colIndex] ?? 0;
                      const clickable = count > 0;
                      return (
                        <td
                          key={`${row}-${col}`}
                          style={cellStyle(count, data.max_cell)}
                          title={
                            clickable
                              ? `${row} × ${col}: ${count} — click to show datasets`
                              : `${row} × ${col}: 0`
                          }
                          className={clickable ? "pivot-cell is-clickable" : "pivot-cell"}
                          role={clickable ? "button" : undefined}
                          tabIndex={clickable ? 0 : undefined}
                          onClick={() => drillIntoCell(row, col, count)}
                          onKeyDown={(event) => {
                            if (!clickable) return;
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              drillIntoCell(row, col, count);
                            }
                          }}
                        >
                          {count || "·"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}

function labelFor(value: string): string {
  return PIVOT_FIELDS.find((field) => field.value === value)?.label ?? value;
}
