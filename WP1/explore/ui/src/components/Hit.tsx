export type ExperimentHit = {
  objectID: string;
  title?: string;
  organism?: string[];
  top_organ?: string[];
  tissue?: string[];
  assay?: string[];
  disease?: string[];
  suspension_type?: string[];
  cell_count?: number;
  feature_count?: number;
  explorer_url?: string;
  experiment_id?: string;
  study_journal?: string;
};

export function hitTitle(hit: ExperimentHit): string {
  return hit.title || hit.experiment_id || hit.objectID;
}

export function joinValues(values?: string[], limit = 3): string {
  if (!values?.length) return "—";
  const shown = values.slice(0, limit);
  const rest = values.length - shown.length;
  return rest > 0 ? `${shown.join(", ")} +${rest}` : shown.join(", ");
}

function chips(values?: string[], limit = 4) {
  if (!values?.length) return <span className="empty-cell">—</span>;
  const shown = values.slice(0, limit);
  const rest = values.length - shown.length;
  return (
    <ul className="chip-row">
      {shown.map((value) => (
        <li key={value}>{value}</li>
      ))}
      {rest > 0 ? <li className="muted">+{rest}</li> : null}
    </ul>
  );
}

export function Hit({ hit }: { hit: ExperimentHit }) {
  const title = hitTitle(hit);
  return (
    <article className="hit">
      <header className="hit-header">
        <h3>
          {hit.explorer_url ? (
            <a href={hit.explorer_url} target="_blank" rel="noreferrer">
              {title}
            </a>
          ) : (
            title
          )}
        </h3>
        <p className="hit-meta">
          <span>{(hit.cell_count ?? 0).toLocaleString()} cells</span>
          {hit.feature_count ? (
            <span>{hit.feature_count.toLocaleString()} features</span>
          ) : null}
          {hit.study_journal && hit.study_journal !== "unknown" ? (
            <span>{hit.study_journal}</span>
          ) : null}
        </p>
      </header>
      <dl className="hit-facets">
        <div>
          <dt>Organism</dt>
          <dd>{chips(hit.organism)}</dd>
        </div>
        <div>
          <dt>Top organ</dt>
          <dd>{chips(hit.top_organ)}</dd>
        </div>
        <div>
          <dt>Tissue</dt>
          <dd>{chips(hit.tissue, 5)}</dd>
        </div>
        <div>
          <dt>Assay</dt>
          <dd>{chips(hit.assay)}</dd>
        </div>
        <div>
          <dt>Disease</dt>
          <dd>{chips(hit.disease)}</dd>
        </div>
      </dl>
    </article>
  );
}
