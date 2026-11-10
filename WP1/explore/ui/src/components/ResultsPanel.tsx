import { useEffect, useState } from "react";
import { useHits } from "react-instantsearch";
import { GROUP_BY_OPTIONS, groupHits, type GroupByField } from "./groupBy";
import { Hit, hitTitle, joinValues, type ExperimentHit } from "./Hit";
import { PivotHeatmap } from "./PivotHeatmap";
import type { ResultsView } from "./ViewToggle";

const GROUP_STORAGE_KEY = "fenix-explore-group-by";

function loadStoredGroupBy(): GroupByField {
  try {
    const value = localStorage.getItem(GROUP_STORAGE_KEY);
    if (GROUP_BY_OPTIONS.some((option) => option.value === value)) {
      return value as GroupByField;
    }
  } catch {
    // ignore
  }
  return "none";
}

type Props = {
  view: ResultsView;
};

function HitRow({ hit }: { hit: ExperimentHit }) {
  const title = hitTitle(hit);
  return (
    <tr>
      <td className="title-cell">
        {hit.explorer_url ? (
          <a href={hit.explorer_url} target="_blank" rel="noreferrer">
            {title}
          </a>
        ) : (
          title
        )}
        {hit.study_journal && hit.study_journal !== "unknown" ? (
          <span className="row-sub">{hit.study_journal}</span>
        ) : null}
      </td>
      <td>{joinValues(hit.organism, 2)}</td>
      <td>{joinValues(hit.top_organ, 2)}</td>
      <td>{joinValues(hit.assay, 2)}</td>
      <td>{joinValues(hit.disease, 2)}</td>
      <td className="num">{(hit.cell_count ?? 0).toLocaleString()}</td>
    </tr>
  );
}

export function ResultsPanel({ view }: Props) {
  const { items } = useHits<ExperimentHit>();
  const [groupBy, setGroupBy] = useState<GroupByField>(() => loadStoredGroupBy());

  useEffect(() => {
    try {
      localStorage.setItem(GROUP_STORAGE_KEY, groupBy);
    } catch {
      // ignore
    }
  }, [groupBy]);

  if (view === "pivot") {
    return <PivotHeatmap />;
  }

  if (!items.length) {
    return <p className="empty-results">No experiments match these filters.</p>;
  }

  if (view === "table") {
    const groups = groupHits(items, groupBy);
    const grouped = groupBy !== "none";

    return (
      <div className="results-table-stack">
        <div className="results-table-toolbar">
          <label className="group-by-control" htmlFor="group-by-select">
            <span className="group-by-label">Group by</span>
            <select
              id="group-by-select"
              value={groupBy}
              onChange={(event) => setGroupBy(event.target.value as GroupByField)}
            >
              {GROUP_BY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <p className="group-by-hint">
            {grouped
              ? "Sections the current page of hits (multi-valued fields may appear in more than one group)."
              : "Choose an attribute to nest rows under section headers."}
          </p>
        </div>

        <div className="results-table-wrap">
          <table className="results-table">
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Organism</th>
                <th scope="col">Top organ</th>
                <th scope="col">Assay</th>
                <th scope="col">Disease</th>
                <th scope="col" className="num">
                  Cells
                </th>
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <GroupSection
                  key={group.key}
                  label={group.label}
                  count={group.hits.length}
                  showHeader={grouped}
                  hits={group.hits}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className="results-card-grid" role="list">
      {items.map((hit) => (
        <div key={hit.objectID} role="listitem">
          <Hit hit={hit} />
        </div>
      ))}
    </div>
  );
}

function GroupSection({
  label,
  count,
  showHeader,
  hits,
}: {
  label: string;
  count: number;
  showHeader: boolean;
  hits: ExperimentHit[];
}) {
  return (
    <>
      {showHeader ? (
        <tr className="group-header-row">
          <th scope="colgroup" colSpan={6}>
            <span className="group-header-label">{label}</span>
            <span className="group-header-count">
              {count} {count === 1 ? "experiment" : "experiments"}
            </span>
          </th>
        </tr>
      ) : null}
      {hits.map((hit) => (
        <HitRow key={`${label}-${hit.objectID}`} hit={hit} />
      ))}
    </>
  );
}
