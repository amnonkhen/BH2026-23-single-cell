import { useHits } from "react-instantsearch";
import { Hit, hitTitle, joinValues, type ExperimentHit } from "./Hit";
import type { ResultsView } from "./ViewToggle";

type Props = {
  view: ResultsView;
};

export function ResultsPanel({ view }: Props) {
  const { items } = useHits<ExperimentHit>();

  if (!items.length) {
    return <p className="empty-results">No experiments match these filters.</p>;
  }

  if (view === "table") {
    return (
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
            {items.map((hit) => {
              const title = hitTitle(hit);
              return (
                <tr key={hit.objectID}>
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
            })}
          </tbody>
        </table>
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
