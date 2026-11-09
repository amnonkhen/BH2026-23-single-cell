# Fenix experiment explore stack

Polished local explore stack for [`WP1/fenix/experiments.json`](../fenix/experiments.json):

| Piece | Role |
|-------|------|
| **Typesense** (Docker Compose) | Faceted search index |
| **Python indexer** | Flattens experiment JSON → Typesense docs |
| **FastAPI** | Holds admin API key, mints search-only key, optional search proxy, MCP-ready tool routes |
| **React + Vite + InstantSearch** | Search box, facets, hits list via `typesense-instantsearch-adapter` |

The browser **never** receives the Typesense admin key. InstantSearch loads `/api/search-config` and uses a **search-only** key.

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+ (for the UI)
- Fenix catalog at `WP1/fenix/experiments.json` (this branch includes it; otherwise run `python3 WP1/fenix/download_experiments.py`)

## Quick start

```bash
cd WP1/explore
cp -n .env.example .env   # optional; defaults work locally

# 1) Typesense
docker compose up -d

# 2) Index experiments
python3 -m venv .venv
source .venv/bin/activate
pip install -r indexer/requirements.txt -r api/requirements.txt
python indexer/index_experiments.py --recreate

# 3) API (search-only keys + MCP stubs)
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

Each experiment becomes one Typesense document with facet fields:

| Field | Source |
|-------|--------|
| `organism` | `organism[].label` |
| `top_organ` | `tissue[].top-organ-name` |
| `tissue` | `tissue[].label` |
| `tissue_type` | `tissue[].tissue_type` |
| `assay` / `disease` / `sex` / … | `*.label` (or string lists) |
| `suspension_type` | string list |
| `study_journal` | journal fields |
| `cell_type` | high-cardinality facet + search |
| `cell_count`, `feature_count`, `published_at` | metrics / sort |
| `search_blob` | concatenated free-text |

Re-index after refreshing the Fenix snapshot:

```bash
python indexer/index_experiments.py --recreate
```

## API & MCP stubs

| Route | Purpose |
|-------|---------|
| `GET /health` | API + Typesense health |
| `GET /api/search-config` | Host/port/collection + **search-only** key for InstantSearch |
| `POST /api/multi_search` | Optional proxy (admin key stays server-side) |
| `GET /mcp/tools` | Tool descriptors (`search_experiments`, `facet_by`) |
| `POST /mcp/tools/search_experiments` | Server-side search tool |
| `POST /mcp/tools/facet_by` | Facet counts for one field |
| `GET /mcp/README` | Notes on wiring a real MCP server |

### Example tool calls

```bash
curl -s 'http://127.0.0.1:8000/mcp/tools/search_experiments?q=brain&per_page=3' | jq '.found'

curl -s -X POST http://127.0.0.1:8000/mcp/tools/facet_by \
  -H 'content-type: application/json' \
  -d '{"field":"top_organ","filter_by":"organism:=`Homo sapiens`"}' | jq .
```

### Wiring a real MCP later

Wrap the same handlers with the MCP Python SDK / FastMCP (`@mcp.tool()` → call the Typesense client), or point an MCP HTTP gateway at these routes. Keep the admin key in the MCP/API process only — see `GET /mcp/README`.

## Layout

```
WP1/explore/
  docker-compose.yml      # Typesense
  .env.example
  indexer/index_experiments.py
  api/main.py             # FastAPI + MCP stubs
  ui/                     # React + Vite + InstantSearch
  README.md
```

## Preference note

This repo’s explore path is **Typesense + React InstantSearch (Vite) + FastAPI** for API keys and MCP/chat tools.
