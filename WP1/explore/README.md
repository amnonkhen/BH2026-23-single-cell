# Unified experiment explore stack (Fenix + Single Cell Portal)

Polished local explore stack over:

- [`WP1/fenix/experiments.json`](../fenix/experiments.json) → `source=fenix`
- [`WP1/single_cell_portal/studies.json`](../single_cell_portal/studies.json) → `source=single_cell_portal`

| Piece | Role |
|-------|------|
| **Typesense** (Docker Compose) | Faceted search index |
| **Python indexer** | Flattens both catalogs → Typesense docs with `source` |
| **FastAPI** | Holds admin API key, mints search-only key, pivot API, MCP-ready tool routes |
| **React + Vite + InstantSearch** | Search, facets, Cards/Table/Pivot; clickable pivot cells |

The browser **never** receives the Typesense admin key. InstantSearch loads `/api/search-config` and uses a **search-only** key.

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+ (for the UI)
- Catalogs:
  - Fenix: `python3 WP1/fenix/download_experiments.py` (or use the cached file)
  - SCP: `python3 WP1/single_cell_portal/download_studies.py --summarize`

## Quick start

```bash
cd WP1/explore
cp -n .env.example .env   # optional; defaults work locally

# 1) Typesense
docker compose up -d

# 2) Index both catalogs into one collection
#    (warms OLS tissue hierarchy cache on first run; Fenix curies + SCP labels)
python3 -m venv .venv
source .venv/bin/activate
pip install -r indexer/requirements.txt -r api/requirements.txt
python indexer/index_experiments.py --recreate

# 3) API (search-only keys + MCP stubs + pivot)
cd api && uvicorn main:app --reload --port 8000
# → http://127.0.0.1:8000/docs

# 4) UI (new terminal)
cd WP1/explore/ui
npm install
npm run dev
# → http://127.0.0.1:5173
```

Vite proxies `/api`, `/mcp`, and `/health` to the FastAPI process. InstantSearch then talks to Typesense on `localhost:8108` with the search-only key from `/api/search-config`.

## What gets indexed

Every document has a faceted **`source`** (`fenix` or `single_cell_portal`) plus shared facet fields:

| Field | Fenix | Single Cell Portal |
|-------|-------|--------------------|
| `organism` | `organism[].label` | `metadata.species` |
| `top_organ` | `tissue[].top-organ-name` | `metadata.organ` (also used as tissue) |
| `tissue` | `tissue[].label` | `metadata.organ` |
| `tissue_hierarchy.lvl0…lvl5` | OLS UBERON path from `tissue[].ontology_term_id` | Best-effort OLS label → UBERON for `metadata.organ` |
| `assay` | `assay[].label` | `metadata.library_preparation_protocol` |
| `disease` | `disease[].label` | `metadata.disease` |
| `cell_type` | `cell_type[].label` | *(not in SCP search API — empty)* |
| `development_stage` | `development_stage[].label` | *(not in SCP search API — empty)* |
| `sex` | `sex[].label` | `metadata.sex` |
| `cell_count` | `cell_count` | `cell_count` |
| `feature_count` | `feature_count` | `gene_count` |
| `explorer_url` | CELLxGENE explorer | SCP study URL |

Document ids are namespaced (`fenix::…`, `scp::SCP####`) to avoid collisions.

Facet string values are **case-normalized** at index time (`canonicalize_facet_value`): case-only variants merge (e.g. `brain`/`Brain` → `Brain`, `10X 3' v2`/`10x 3' v2` → `10x 3' v2`).

### Tissue hierarchy (OLS)

At index time the indexer resolves tissues via [EBI OLS4](https://www.ebi.ac.uk/ols4/) and writes Algolia-style `tissue_hierarchy.lvlN` fields (`"Organ > Substructure > …"`). The UI uses InstantSearch **HierarchicalMenu** for browse, and keeps a collapsed flat **Tissue** facet for search/keyword use.

| Source | Resolution |
|--------|------------|
| **Fenix** (primary) | `tissue[].ontology_term_id` (and `top-organ-uberon`) → OLS UBERON jstree path |
| **SCP** (best-effort) | exact OLS label search on `metadata.organ`; falls back to a single-level path |

Responses are cached on disk at `indexer/ols_cache/uberon_paths.json` so re-indexes do not hammer OLS.

**Refresh the OLS cache** (e.g. after new tissues appear in the catalogs, or to pick up ontology updates):

```bash
cd WP1/explore
source .venv/bin/activate

# Standalone warm (Fenix curies; add --scp for SCP organ labels)
python indexer/enrich_tissue_hierarchy.py --scp

# Force re-fetch from OLS (ignore existing cache entries)
python indexer/enrich_tissue_hierarchy.py --refresh --scp

# Or refresh while indexing
python indexer/index_experiments.py --recreate --refresh-ols

# Skip hierarchy enrichment entirely
python indexer/index_experiments.py --recreate --skip-ols
```

Then re-index so Typesense docs pick up the new paths:

```bash
python indexer/index_experiments.py --recreate
```

Re-index after refreshing either catalog snapshot as well (same command).

## UI views

- **Cards / Table** — InstantSearch hits; Table has **Group by** section headers
- **Pivot** — row × column heatmap of dataset counts (respects query + facets). **Click a cell** to apply InstantSearch filters for those attribute values and switch to **Table**
- **Tissue hierarchy** — InstantSearch HierarchicalMenu over `tissue_hierarchy.lvl*`; flat tissue facet still available

## API & MCP stubs

| Route | Purpose |
|-------|---------|
| `GET /health` | API + Typesense health |
| `GET /api/search-config` | Host/port/collection + **search-only** key for InstantSearch |
| `POST /api/multi_search` | Optional proxy (admin key stays server-side) |
| `POST /api/pivot` | Row × column dataset counts |
| `GET /mcp/tools` | Tool descriptors (`search_experiments`, `facet_by`) |
| `POST /mcp/tools/search_experiments` | Server-side search tool |
| `POST /mcp/tools/facet_by` | Facet counts for one field |
| `GET /mcp/README` | Notes on wiring a real MCP server |

### Example tool calls

```bash
curl -s -X POST http://127.0.0.1:8000/mcp/tools/facet_by \
  -H 'content-type: application/json' \
  -d '{"field":"source"}' | jq .

curl -s -X POST http://127.0.0.1:8000/api/pivot \
  -H 'content-type: application/json' \
  -d '{"row_field":"source","col_field":"organism","max_rows":10,"max_cols":10}' | jq '{found,rows,cols,max_cell}'
```

### Wiring a real MCP later

Wrap the same handlers with the MCP Python SDK / FastMCP (`@mcp.tool()` → call the Typesense client), or point an MCP HTTP gateway at these routes. Keep the admin key in the MCP/API process only — see `GET /mcp/README`.

## Layout

```
WP1/explore/
  docker-compose.yml
  .env.example
  indexer/
    index_experiments.py
    ols_tissue.py
    enrich_tissue_hierarchy.py
    ols_cache/uberon_paths.json   # OLS hierarchy cache (refreshable)
  api/main.py
  ui/
  README.md
WP1/fenix/                 # Fenix catalog cache
WP1/single_cell_portal/    # SCP catalog cache
```

## Preference note

Explore path: **Typesense + React InstantSearch (Vite) + FastAPI** for API keys and MCP/chat tools, with a unified multi-source index.
