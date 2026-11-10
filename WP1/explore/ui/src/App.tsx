import { useEffect, useState } from "react";
import {
  ClearRefinements,
  Configure,
  CurrentRefinements,
  InstantSearch,
  Pagination,
  RefinementList,
  SearchBox,
  Stats,
} from "react-instantsearch";
import { ResultsPanel } from "./components/ResultsPanel";
import { ViewToggle, type ResultsView } from "./components/ViewToggle";
import { createSearchClient, loadSearchConfig, type SearchConfig } from "./typesense";

const FACET_PANELS: { attribute: string; title: string; searchable?: boolean }[] = [
  { attribute: "source", title: "Source" },
  { attribute: "organism", title: "Organism" },
  { attribute: "top_organ", title: "Top organ", searchable: true },
  { attribute: "tissue", title: "Tissue", searchable: true },
  { attribute: "tissue_type", title: "Tissue type" },
  { attribute: "assay", title: "Assay", searchable: true },
  { attribute: "disease", title: "Disease", searchable: true },
  { attribute: "suspension_type", title: "Suspension" },
  { attribute: "sex", title: "Sex" },
  { attribute: "study_journal", title: "Journal", searchable: true },
];

const VIEW_STORAGE_KEY = "fenix-explore-results-view";

function loadStoredView(): ResultsView {
  try {
    const value = localStorage.getItem(VIEW_STORAGE_KEY);
    if (value === "cards" || value === "table" || value === "pivot") return value;
  } catch {
    // ignore private-mode / SSR storage failures
  }
  return "cards";
}

type ReadyState = {
  config: SearchConfig;
  searchClient: ReturnType<typeof createSearchClient>["searchClient"];
  indexName: string;
};

export default function App() {
  const [ready, setReady] = useState<ReadyState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ResultsView>(() => loadStoredView());

  useEffect(() => {
    let cancelled = false;
    loadSearchConfig()
      .then((config) => {
        if (cancelled) return;
        const { searchClient, indexName } = createSearchClient(config);
        setReady({ config, searchClient, indexName });
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(
            err.message +
              " — start the FastAPI backend (`uvicorn main:app`) and Typesense first."
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, view);
    } catch {
      // ignore
    }
  }, [view]);

  if (error) {
    return (
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">WP1 · Fenix</p>
          <h1>Experiment explore</h1>
        </header>
        <p className="error">{error}</p>
      </main>
    );
  }

  if (!ready) {
    return (
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">WP1 · Fenix</p>
          <h1>Experiment explore</h1>
          <p className="lede">Loading search configuration…</p>
        </header>
      </main>
    );
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">WP1 · Fenix / CELLxGENE</p>
        <h1>Experiment explore</h1>
        <p className="lede">
          Faceted search over the Fenix experiment catalog. Keys stay on the
          FastAPI side; InstantSearch uses a search-only Typesense key.
        </p>
      </header>

      <InstantSearch
        searchClient={ready.searchClient}
        indexName={ready.indexName}
        future={{ preserveSharedStateOnUnmount: true }}
      >
        <Configure
          hitsPerPage={12}
          facetFilters={[]}
          attributesToRetrieve={[
            "title",
            "source",
            "organism",
            "top_organ",
            "tissue",
            "assay",
            "disease",
            "suspension_type",
            "cell_count",
            "feature_count",
            "explorer_url",
            "experiment_id",
            "study_journal",
          ]}
        />

        <section className="toolbar">
          <SearchBox
            placeholder="Search title, tissue, assay, cell type…"
            autoFocus
          />
          <div className="toolbar-meta">
            <Stats />
            <div className="toolbar-actions">
              <ViewToggle value={view} onChange={setView} />
              <ClearRefinements translations={{ resetButtonText: "Clear filters" }} />
            </div>
          </div>
          <CurrentRefinements />
        </section>

        <div className="layout">
          <aside className="facets">
            {FACET_PANELS.map((panel) => (
              <details key={panel.attribute} open={panel.attribute !== "study_journal"}>
                <summary>{panel.title}</summary>
                <RefinementList
                  attribute={panel.attribute}
                  searchable={panel.searchable}
                  showMore
                  limit={8}
                  searchablePlaceholder={`Filter ${panel.title.toLowerCase()}…`}
                />
              </details>
            ))}
          </aside>

          <section className="results" data-view={view}>
            <ResultsPanel
              view={view}
              onOpenHits={() => setView("table")}
            />
            {view !== "pivot" ? <Pagination /> : null}
          </section>
        </div>
      </InstantSearch>
    </main>
  );
}
