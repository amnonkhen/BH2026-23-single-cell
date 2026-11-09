# Fenix / CELLxGENE experiment catalog (WP1)

Snapshot of experiment metadata from the EBI Fenix wwwdev API, for dataset discovery and facet exploration in WP1.

## Contents

| File | Purpose |
|------|---------|
| [`download_experiments.py`](download_experiments.py) | Reproducible download + schema/facet summary |
| [`download_experiments.sh`](download_experiments.sh) | Thin shell wrapper |
| [`experiments.json`](experiments.json) | Full API payload (`{"data":[...], "total": N}`) |
| [`experiments.sample.json`](experiments.sample.json) | First 2 records (easy to skim) |
| [`experiments.schema-summary.json`](experiments.schema-summary.json) | Field list + facet cardinalities |

Repo root `.gitignore` ignores generic `data/` trees (large H5AD etc.). This catalog lives under `WP1/fenix/` so the ~6 MiB JSON can be versioned with the scripts.

## Refresh

```bash
python3 WP1/fenix/download_experiments.py
# or
WP1/fenix/download_experiments.sh --summarize
```

Source URL (default):

`https://wwwdev.ebi.ac.uk/fenix/api/experiments?page=1&perPage=10000&sortField=title&sortOrder=ASC&include_journals=true`

At snapshot time: **429** experiments, API `total=429`, file ~**6.2 MiB**. If `total` grows past `perPage`, raise `perPage` or extend the script to paginate.

## JSON shape (facets)

Top level: `data` (list of experiments), `total` (int).

Each experiment is CELLxGENE-like curated metadata. Ontology-backed attributes are usually `list[{label, ontology_term_id}]`. Multi-valued fields are common (`tissue`, `assay`, `cell_type`, …).

### Best facet / aggregation attributes

| Attribute | Unique values (snapshot) | Notes |
|-----------|--------------------------:|-------|
| `organism.label` | 5 | Single-valued per dataset; primary species filter |
| `tissue.top-organ-name` | 39 | Coarser than tissue label; good **group-by** |
| `tissue.label` | 317 | Fine anatomy; good **filter**, noisy for charts |
| `tissue.tissue_type` | 3 | `tissue` / `organoid` / `primary cell culture` |
| `assay.label` | 21 | Technology facet |
| `disease.label` | 74 | Dominated by `normal` (~402 datasets) |
| `suspension_type` | 2 | `cell` vs `nucleus` |
| `sex.label` | 3 | Often multi-valued within a dataset |
| `study_journal` / `journal_resolution.long_name` | ~25–31 | Publication venue |
| `cell_type.label` | 698 | High cardinality; better as search or secondary facet |
| `development_stage.label` | 195 | High cardinality; consider ontology roll-up later |
| `self_reported_ethnicity.label` | 19 | Many `unknown` / `na` |

Useful metrics (not categorical facets): `cell_count`, `primary_cell_count`, `feature_count`, `mean_genes_per_cell`, `published_at`.

Identifiers / links: `experiment_id`, `study_id`, `explorer_url`, `assets[].url` (H5AD).

### Example filter → group patterns

1. **Filter** `organism=Homo sapiens` → **group by** `tissue.top-organ-name` (dataset counts or Σ `cell_count`).
2. **Filter** `tissue.top-organ-name=brain` → **group by** `assay.label`.
3. **Filter** `disease≠normal` → **group by** `organism` or `study_journal`.
4. **Filter** `suspension_type=nucleus` → **group by** `tissue.top-organ-name`.

## Implemented explore stack

**Typesense + React InstantSearch + FastAPI (MCP-ready)** is scaffolded in [`../explore/`](../explore/). See that README for `compose up` → index → API → UI.

## Proposed search UI stacks (context / alternatives)

Goal: filter datasets by one attribute (e.g. tissue) and aggregate/group by another. Catalog size (~429 rows, ~6 MiB) fits **fully client-side** or a tiny local backend.


### 1. Python FastAPI + React (recommended default)

- **Local:** FastAPI serves `experiments.json` (or a slim projection) and optional aggregation endpoints; React UI for facet pickers + bar/table aggregates.
- **Hosted:** same stack on any small PaaS; static React build + API.
- **Pros:** Matches project Python tooling; clear path to ontology roll-ups and WP1 query tools; full UI control.
- **Cons:** More scaffolding than a notebook app; need a short API contract.
- **Fit:** Excellent for this data size; scale later by swapping JSON for SQLite/Parquet.

### 2. Datasette (SQLite) ± lite front-end

- Load flattened facets into SQLite; Datasette gives **automatic facets**, SQL, and CSV export with almost no UI code.
- **Pros:** Fastest path to “filter + group” exploration; great for BioHackathon demos.
- **Cons:** Less custom UX; multi-valued ontology fields need a tidy long-table schema.
- **Fit:** Ideal for local exploration of this catalog; hosting via Datasette Cloud or a tiny VPS is optional.

### 3. Streamlit or Panel (Python-only)

- Single Python process: widgets for filter attribute/value, Altair/Plotly for group-by charts.
- **Pros:** Lowest engineering cost for the team; same env as WP1/WP2.
- **Cons:** Weaker multi-facet search UX; harder to embed as a polished public portal.
- **Fit:** Best for a same-day prototype; graduate to FastAPI+React if the UI sticks.

### 4. Meilisearch or Typesense + React

- Index a flattened document per experiment; use built-in **faceted search**; React consumes search/facet APIs.
- **Pros:** Best typeahead + multi-facet UX; local Docker or hosted SaaS.
- **Cons:** Extra service to run; overkill unless free-text search across `title`/`search_text`/`cell_type` is central.
- **Fit:** Still fine at 429 docs; shines if the catalog grows or merges multiple repositories.

### Quick comparison

| Stack | Local ease | Hosted ease | Facets | Data-size fit |
|-------|------------|-------------|--------|---------------|
| FastAPI + React | Medium | Medium | Custom, flexible | Excellent |
| Datasette | High | Medium | Built-in | Excellent |
| Streamlit / Panel | Highest | Medium | Widget-based | Excellent |
| Meilisearch/Typesense + React | Medium | High (SaaS) | First-class | Excellent (future-proof) |

**Suggestion for WP1:** start with **Datasette or Streamlit** to validate facet choices on this snapshot, then implement the lasting UI as **FastAPI + React** if we need a shareable portal. Reach for Meilisearch/Typesense only if free-text + many simultaneous facets become the main interaction.
