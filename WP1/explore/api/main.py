#!/usr/bin/env python3
"""FastAPI gateway for Fenix experiment search.

Holds the Typesense admin key server-side, mints a search-only key for the
React InstantSearch UI, optionally proxies search, and exposes MCP-ready
tool routes (`search_experiments`, `facet_by`).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import typesense
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.example", override=False)

COLLECTION = os.getenv("TYPESENSE_COLLECTION", "experiments")
TYPESENSE_HOST = os.getenv("TYPESENSE_HOST", "localhost")
TYPESENSE_PORT = os.getenv("TYPESENSE_PORT", "8108")
TYPESENSE_PROTOCOL = os.getenv("TYPESENSE_PROTOCOL", "http")
ADMIN_KEY = os.getenv("TYPESENSE_API_KEY", "bh2026-typesense-admin-key")
SEARCH_KEY_DESCRIPTION = os.getenv(
    "TYPESENSE_SEARCH_KEY_DESCRIPTION", "bh2026-explore-search-only"
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

FACET_FIELDS = [
    "organism",
    "top_organ",
    "tissue",
    "tissue_type",
    "assay",
    "disease",
    "suspension_type",
    "sex",
    "development_stage",
    "self_reported_ethnicity",
    "study_journal",
    "cell_type",
]

app = FastAPI(
    title="Fenix experiment explore API",
    description=(
        "Typesense-backed search for WP1/fenix experiments. "
        "Browser clients receive a search-only key; admin key stays here. "
        "MCP tool stubs live under /mcp/tools/*."
    ),
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_search_key_cache: str | None = None


def typesense_client(api_key: str | None = None) -> typesense.Client:
    return typesense.Client(
        {
            "nodes": [
                {
                    "host": TYPESENSE_HOST,
                    "port": TYPESENSE_PORT,
                    "protocol": TYPESENSE_PROTOCOL,
                }
            ],
            "api_key": api_key or ADMIN_KEY,
            "connection_timeout_seconds": 15,
        }
    )


def typesense_base_url() -> str:
    return f"{TYPESENSE_PROTOCOL}://{TYPESENSE_HOST}:{TYPESENSE_PORT}"


def get_or_create_search_key() -> str:
    """Mint a collection-scoped search-only API key (cached in-process).

    Typesense only returns the secret on create, not on list — so each API
    process creates one key and reuses it until restart.
    """
    global _search_key_cache
    if _search_key_cache:
        return _search_key_cache

    client = typesense_client()
    created = client.keys.create(
        {
            "description": SEARCH_KEY_DESCRIPTION,
            "actions": ["documents:search"],
            "collections": [COLLECTION],
        }
    )
    value = created.get("value")
    if not value:
        raise RuntimeError("Typesense did not return a search key value")
    _search_key_cache = value
    return value


class SearchConfig(BaseModel):
    host: str
    port: int
    protocol: str
    collection: str
    api_key: str = Field(description="Search-only Typesense key")
    nearest_nodes: list[dict[str, Any]] = Field(default_factory=list)
    query_by: str = "title,search_blob,cell_type,tissue,assay,disease,organism"
    facet_by: list[str] = Field(default_factory=lambda: list(FACET_FIELDS))
    note: str = (
        "Use InstantSearch + typesense-instantsearch-adapter with this config. "
        "Do not request the admin key from the browser."
    )


class SearchRequest(BaseModel):
    q: str = "*"
    query_by: str = "title,search_blob,cell_type,tissue,assay,disease,organism"
    filter_by: str | None = None
    facet_by: str | None = None
    max_facet_values: int = 50
    per_page: int = 20
    page: int = 1
    sort_by: str | None = "cell_count:desc"


class FacetByRequest(BaseModel):
    field: str
    q: str = "*"
    filter_by: str | None = None
    max_facet_values: int = 50


class PivotRequest(BaseModel):
    row_field: str
    col_field: str
    q: str = "*"
    filter_by: str | None = None
    max_rows: int = Field(default=20, ge=1, le=50)
    max_cols: int = Field(default=20, ge=1, le=50)
    query_by: str = "title,search_blob,cell_type,tissue,assay,disease,organism"


class McpToolDescriptor(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


def _field_values(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            text = str(item).strip()
            if text and text != "unknown" and text not in seen:
                seen.add(text)
                out.append(text)
        return out
    text = str(raw).strip()
    if text and text != "unknown":
        return [text]
    return []


def build_pivot(
    docs: list[dict[str, Any]],
    *,
    row_field: str,
    col_field: str,
    max_rows: int,
    max_cols: int,
) -> dict[str, Any]:
    """Cross-tab unique experiment counts for two facet fields."""
    cell_ids: dict[tuple[str, str], set[str]] = {}
    row_ids: dict[str, set[str]] = {}
    col_ids: dict[str, set[str]] = {}

    for doc in docs:
        doc_id = str(doc.get("id") or doc.get("experiment_id") or id(doc))
        rows = _field_values(doc.get(row_field)) or ["(none)"]
        cols = _field_values(doc.get(col_field)) or ["(none)"]
        for row in rows:
            row_ids.setdefault(row, set()).add(doc_id)
            for col in cols:
                col_ids.setdefault(col, set()).add(doc_id)
                cell_ids.setdefault((row, col), set()).add(doc_id)

    ranked_rows = sorted(
        row_ids.items(),
        key=lambda item: (-len(item[1]), item[0] == "(none)", item[0].lower()),
    )
    ranked_cols = sorted(
        col_ids.items(),
        key=lambda item: (-len(item[1]), item[0] == "(none)", item[0].lower()),
    )
    selected_rows = [name for name, _ in ranked_rows[:max_rows]]
    selected_cols = [name for name, _ in ranked_cols[:max_cols]]

    matrix = [
        [len(cell_ids.get((row, col), set())) for col in selected_cols]
        for row in selected_rows
    ]
    row_totals = [len(row_ids[row]) for row in selected_rows]
    col_totals = [len(col_ids[col]) for col in selected_cols]
    max_cell = max((value for row in matrix for value in row), default=0)

    return {
        "row_field": row_field,
        "col_field": col_field,
        "rows": selected_rows,
        "cols": selected_cols,
        "matrix": matrix,
        "row_totals": row_totals,
        "col_totals": col_totals,
        "max_cell": max_cell,
        "truncated_rows": max(0, len(ranked_rows) - len(selected_rows)),
        "truncated_cols": max(0, len(ranked_cols) - len(selected_cols)),
        "docs_scanned": len(docs),
    }


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        ok = typesense_client().operations.is_healthy()
        healthy = ok is True or (isinstance(ok, dict) and ok.get("ok") is True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Typesense unhealthy: {exc}") from exc
    return {"ok": True, "typesense": healthy, "collection": COLLECTION}


@app.get("/api/search-config", response_model=SearchConfig)
def search_config() -> SearchConfig:
    """Config for the Vite InstantSearch UI (search-only key only)."""
    try:
        api_key = get_or_create_search_key()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SearchConfig(
        host=TYPESENSE_HOST,
        port=int(TYPESENSE_PORT),
        protocol=TYPESENSE_PROTOCOL,
        collection=COLLECTION,
        api_key=api_key,
        nearest_nodes=[],
        facet_by=list(FACET_FIELDS),
    )


@app.post("/api/multi_search")
async def proxy_multi_search(payload: dict[str, Any]) -> Any:
    """Optional proxy so the browser never talks to Typesense directly."""
    url = f"{typesense_base_url()}/multi_search"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            params={"x-typesense-api-key": ADMIN_KEY},
            headers={"X-TYPESENSE-API-KEY": ADMIN_KEY},
            json=payload,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@app.post("/api/pivot")
def pivot_counts(body: PivotRequest) -> Any:
    """Row × column dataset counts for two facet fields (heatmap/pivot).

    Respects Typesense `q` + `filter_by` so InstantSearch refinements can be
    forwarded from the UI. Multi-valued fields contribute to each matching cell.
    """
    if body.row_field not in FACET_FIELDS or body.col_field not in FACET_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"row_field and col_field must be one of: {FACET_FIELDS}",
        )
    if body.row_field == body.col_field:
        raise HTTPException(
            status_code=400, detail="row_field and col_field must be different"
        )

    client = typesense_client()
    include_fields = ",".join(
        sorted({"id", "experiment_id", body.row_field, body.col_field})
    )
    page = 1
    per_page = 250
    docs: list[dict[str, Any]] = []
    found = 0
    try:
        while True:
            params: dict[str, Any] = {
                "q": body.q or "*",
                "query_by": body.query_by,
                "per_page": per_page,
                "page": page,
                "include_fields": include_fields,
            }
            if body.filter_by:
                params["filter_by"] = body.filter_by
            result = client.collections[COLLECTION].documents.search(params)
            found = int(result.get("found") or 0)
            hits = result.get("hits") or []
            for hit in hits:
                doc = hit.get("document") or {}
                if isinstance(doc, dict):
                    docs.append(doc)
            if page * per_page >= found or not hits:
                break
            page += 1
            if page > 20:  # hard stop (~5k docs) for safety
                break
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    pivot = build_pivot(
        docs,
        row_field=body.row_field,
        col_field=body.col_field,
        max_rows=body.max_rows,
        max_cols=body.max_cols,
    )
    pivot.update(
        {
            "found": found,
            "q": body.q or "*",
            "filter_by": body.filter_by,
        }
    )
    return pivot


@app.get("/mcp/tools", response_model=list[McpToolDescriptor])
def list_mcp_tools() -> list[McpToolDescriptor]:
    """Descriptors for MCP-style tools (wire to a real MCP server later)."""
    return [
        McpToolDescriptor(
            name="search_experiments",
            description=(
                "Full-text + faceted search over Fenix/CELLxGENE experiments "
                "indexed in Typesense."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "q": {"type": "string", "default": "*"},
                    "filter_by": {
                        "type": "string",
                        "description": "Typesense filter_by, e.g. organism:=`Homo sapiens`",
                    },
                    "facet_by": {
                        "type": "string",
                        "description": "Comma-separated facet fields",
                    },
                    "per_page": {"type": "integer", "default": 20},
                    "page": {"type": "integer", "default": 1},
                    "sort_by": {"type": "string", "default": "cell_count:desc"},
                },
            },
        ),
        McpToolDescriptor(
            name="facet_by",
            description=(
                "Return facet counts for one field (organism, top_organ, tissue, "
                "assay, disease, …), optionally with a filter_by clause."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "enum": FACET_FIELDS,
                    },
                    "q": {"type": "string", "default": "*"},
                    "filter_by": {"type": "string"},
                    "max_facet_values": {"type": "integer", "default": 50},
                },
                "required": ["field"],
            },
        ),
    ]


@app.post("/mcp/tools/search_experiments")
def mcp_search_experiments(body: SearchRequest) -> Any:
    client = typesense_client()
    params: dict[str, Any] = {
        "q": body.q or "*",
        "query_by": body.query_by,
        "per_page": body.per_page,
        "page": body.page,
    }
    if body.filter_by:
        params["filter_by"] = body.filter_by
    if body.facet_by:
        params["facet_by"] = body.facet_by
        params["max_facet_values"] = body.max_facet_values
    if body.sort_by:
        params["sort_by"] = body.sort_by
    try:
        return client.collections[COLLECTION].documents.search(params)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/mcp/tools/facet_by")
def mcp_facet_by(body: FacetByRequest) -> Any:
    if body.field not in FACET_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown facet field '{body.field}'. Choose from: {FACET_FIELDS}",
        )
    client = typesense_client()
    params: dict[str, Any] = {
        "q": body.q or "*",
        "query_by": "title,search_blob",
        "facet_by": body.field,
        "max_facet_values": body.max_facet_values,
        "per_page": 0,
    }
    if body.filter_by:
        params["filter_by"] = body.filter_by
    try:
        result = client.collections[COLLECTION].documents.search(params)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    counts = []
    for facet in result.get("facet_counts") or []:
        if facet.get("field_name") == body.field:
            counts = facet.get("counts") or []
            break
    return {
        "field": body.field,
        "counts": counts,
        "found": result.get("found"),
        "filter_by": body.filter_by,
    }


@app.get("/mcp/tools/search_experiments")
def mcp_search_experiments_get(
    q: str = Query("*"),
    filter_by: str | None = None,
    facet_by: str | None = None,
    per_page: int = 20,
    page: int = 1,
) -> Any:
    return mcp_search_experiments(
        SearchRequest(
            q=q,
            filter_by=filter_by,
            facet_by=facet_by,
            per_page=per_page,
            page=page,
        )
    )


MCP_WIRING_NOTE = """
How to wire a real MCP server later
-----------------------------------
Option A — FastMCP / official MCP Python SDK wrapping these handlers:

    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("fenix-explore")

    @mcp.tool()
    def search_experiments(q: str = "*", filter_by: str | None = None, ...):
        return mcp_search_experiments(SearchRequest(...))

    @mcp.tool()
    def facet_by(field: str, filter_by: str | None = None, ...):
        return mcp_facet_by(FacetByRequest(field=field, filter_by=filter_by))

    # stdio: mcp.run()
    # or mount SSE/HTTP transport next to this FastAPI app

Option B — Keep these HTTP routes and point an MCP gateway / Cursor MCP
config at http://localhost:8000/mcp/tools/* as custom tools.

The admin Typesense key must stay in the MCP/API process — never ship it to
the chat UI or browser InstantSearch client.
""".strip()


@app.get("/mcp/README")
def mcp_readme() -> dict[str, str]:
    return {"markdown": MCP_WIRING_NOTE}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
    )
