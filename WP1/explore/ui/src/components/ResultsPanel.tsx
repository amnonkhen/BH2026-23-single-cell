import { useEffect, useMemo, useState } from "react";
import { useHits, useInstantSearch } from "react-instantsearch";
import { GROUP_BY_OPTIONS, groupHits, type GroupByField } from "./groupBy";
import { Hit, hitTitle, joinValues, type ExperimentHit } from "./Hit";
import { PivotHeatmap } from "./PivotHeatmap";
import type { ResultsView } from "./ViewToggle";

const GROUP_STORAGE_KEY = "fenix-explore-group-by";
const NONE_LABEL = "(none)";

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

function groupDomId(key: string): string {
  const slug = key
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80);
  return `group-section-${slug || "none"}`;
}

type Props = {
  view: ResultsView;
  onOpenHits: () => void;
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
      <td>{hit.source || "—"}</td>
      <td>{joinValues(hit.organism, 2)}</td>
      <td>{joinValues(hit.top_organ, 2)}</td>
      <td>{joinValues(hit.assay, 2)}</td>
      <td>{joinValues(hit.disease, 2)}</td>
      <td>{joinValues(hit.cell_type, 2)}</td>
      <td>{joinValues(hit.development_stage, 2)}</td>
      <td className="num">{(hit.cell_count ?? 0).toLocaleString()}</td>
    </tr>
  );
}

export function ResultsPanel({ view, onOpenHits }: Props) {
  const { items } = useHits<ExperimentHit>();
  const { setIndexUiState } = useInstantSearch();
  const [groupBy, setGroupBy] = useState<GroupByField>(() => loadStoredGroupBy());
  const [activeChip, setActiveChip] = useState<string | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(GROUP_STORAGE_KEY, groupBy);
    } catch {
      // ignore
    }
    setActiveChip(null);
  }, [groupBy]);

  const groups = useMemo(
    () => (view === "table" ? groupHits(items, groupBy) : []),
    [view, items, groupBy]
  );

  const topGroups = useMemo(() => {
    if (groupBy === "none") return [];
    return [...groups]
      .sort((a, b) => {
        const byCount = b.hits.length - a.hits.length;
        if (byCount !== 0) return byCount;
        return a.label.localeCompare(b.label, undefined, { sensitivity: "base" });
      })
      .slice(0, 10);
  }, [groups, groupBy]);

  const focusGroup = (key: string, label: string) => {
    setActiveChip(key);

    const el = document.getElementById(groupDomId(key));
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    if (groupBy === "none" || label === NONE_LABEL) return;

    setIndexUiState((previous) => ({
      ...previous,
      page: 1,
      refinementList: {
        ...(previous.refinementList ?? {}),
        [groupBy]: [label],
      },
    }));
  };

  if (view === "pivot") {
    return <PivotHeatmap onOpenHits={onOpenHits} />;
  }

  if (!items.length) {
    return <p className="empty-results">No experiments match these filters.</p>;
  }

  if (view === "table") {
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
              ? "Top groups by count on this page — click a chip to scroll and filter InstantSearch."
              : "Choose an attribute to nest rows under section headers."}
          </p>

          {grouped && topGroups.length > 0 ? (
            <div className="group-chips" role="list" aria-label="Top groups by dataset count">
              {topGroups.map((group) => {
                const selected = activeChip === group.key;
                return (
                  <button
                    key={group.key}
                    type="button"
                    role="listitem"
                    className={selected ? "group-chip is-active" : "group-chip"}
                    title={`${group.label} — ${group.hits.length} on this page; click to scroll & filter`}
                    onClick={() => focusGroup(group.key, group.label)}
                  >
                    <span className="group-chip-label">{group.label}</span>
                    <span className="group-chip-count">{group.hits.length}</span>
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>

        <div className="results-table-wrap">
          <table className="results-table">
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Source</th>
                <th scope="col">Organism</th>
                <th scope="col">Top organ</th>
                <th scope="col">Assay</th>
                <th scope="col">Disease</th>
                <th scope="col">Cell type</th>
                <th scope="col">Dev. stage</th>
                <th scope="col" className="num">
                  Cells
                </th>
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <GroupSection
                  key={group.key}
                  id={groupDomId(group.key)}
                  label={group.label}
                  count={group.hits.length}
                  showHeader={grouped}
                  highlighted={activeChip === group.key}
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
  id,
  label,
  count,
  showHeader,
  highlighted,
  hits,
}: {
  id: string;
  label: string;
  count: number;
  showHeader: boolean;
  highlighted: boolean;
  hits: ExperimentHit[];
}) {
  return (
    <>
      {showHeader ? (
        <tr
          id={id}
          className={
            highlighted ? "group-header-row is-highlighted" : "group-header-row"
          }
        >
          <th scope="colgroup" colSpan={9}>
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
