#!/usr/bin/env python3
"""Flatten Fenix + Single Cell Portal catalogs into one Typesense collection.

Every document includes a faceted `source` field:
  - fenix
  - single_cell_portal
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
import typesense
from typesense.exceptions import ObjectAlreadyExists, ObjectNotFound

from ols_tissue import (
    MAX_LEVELS as TISSUE_HIER_MAX_LEVELS,
    load_cache as load_ols_cache,
    paths_to_hierarchy_fields,
    resolve_path,
    warm_cache_for_curies,
    warm_cache_for_labels,
)

ROOT = Path(__file__).resolve().parents[1]
WP1 = ROOT.parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.example", override=False)

COLLECTION = os.getenv("TYPESENSE_COLLECTION", "experiments")
DEFAULT_FENIX_JSON = Path(
    os.getenv("EXPERIMENTS_JSON", str(WP1 / "fenix" / "experiments.json"))
)
DEFAULT_SCP_JSON = Path(
    os.getenv(
        "SCP_STUDIES_JSON", str(WP1 / "single_cell_portal" / "studies.json")
    )
)

SOURCE_FENIX = "fenix"
SOURCE_SCP = "single_cell_portal"
SCP_ORIGIN = "https://singlecell.broadinstitute.org"

FACET_FIELDS = [
    "source",
    "organism",
    "top_organ",
    "tissue",
    "tissue_type",
    "tissue_hierarchy.lvl0",
    "tissue_hierarchy.lvl1",
    "tissue_hierarchy.lvl2",
    "tissue_hierarchy.lvl3",
    "tissue_hierarchy.lvl4",
    "tissue_hierarchy.lvl5",
    "assay",
    "disease",
    "suspension_type",
    "sex",
    "development_stage",
    "self_reported_ethnicity",
    "study_journal",
    "cell_type",
]

# Acronyms / tokens kept upper (or special-cased) inside Title Case facets.
_UPPER_TOKENS = {
    "tcr",
    "bcr",
    "atac",
    "rna",
    "dna",
    "scrna",
    "snrna",
    "hto",
    "adt",
    "citeseq",
    "multiome",
}
_SPECIAL_TOKENS = {
    "mrna": "mRNA",
    "cdna": "cDNA",
    "scrna-seq": "scRNA-seq",
    "snrna-seq": "snRNA-seq",
    "dronc-seq": "DroNc-seq",
    "drop-seq": "Drop-seq",
}


def canonicalize_facet_value(text: str) -> str:
    """Merge case-only variants into a stable Title Case-ish canonical form.

    Examples:
      'homo sapiens' / 'Homo Sapiens' → 'Homo Sapiens'
      '10X 3' v2' / '10x 3' v2' → \"10x 3' v2\"
      'brain' / 'Brain' → 'Brain'
    """
    raw = " ".join(str(text).strip().split())
    if not raw:
        return raw

    parts: list[str] = []
    for token in raw.split(" "):
        if not token:
            continue
        lower = token.lower()
        special = _SPECIAL_TOKENS.get(lower)
        if special:
            parts.append(special)
            continue
        # 10X / 10x brand → always 10x
        if lower == "10x":
            parts.append("10x")
            continue
        if lower.startswith("10x") and len(token) > 3:
            parts.append("10x" + canonicalize_facet_value(token[3:]))
            continue
        # version tokens: v2, v3, v3.1
        if lower.startswith("v") and len(lower) > 1 and lower[1].isdigit():
            parts.append(lower)
            continue
        # hyphenated compounds: title-case each piece
        if "-" in token:
            pieces = []
            for piece in lower.split("-"):
                if not piece:
                    pieces.append(piece)
                elif piece in _UPPER_TOKENS:
                    pieces.append(piece.upper())
                elif piece in _SPECIAL_TOKENS:
                    pieces.append(_SPECIAL_TOKENS[piece])
                else:
                    pieces.append(piece[:1].upper() + piece[1:])
            parts.append("-".join(pieces))
            continue
        if lower in _UPPER_TOKENS:
            parts.append(lower.upper())
            continue
        # Default Title Case word
        parts.append(lower[:1].upper() + lower[1:])
    return " ".join(parts)


def labels(value: Any, extra_keys: Iterable[str] = ()) -> list[str]:
    """Extract unique label strings from ontology objects, strings, or lists."""
    out: list[str] = []
    seen: set[str] = set()  # casefold keys after canonicalize

    def add(item: str | None) -> None:
        if not item:
            return
        text = canonicalize_facet_value(str(item))
        key = text.casefold()
        if not text or key in seen:
            return
        seen.add(key)
        out.append(text)

    if value is None:
        return out
    if isinstance(value, str):
        add(value)
        return out
    if isinstance(value, dict):
        add(value.get("label"))
        for key in extra_keys:
            add(value.get(key))
        return out
    if isinstance(value, list):
        for item in value:
            for label in labels(item, extra_keys=extra_keys):
                add(label)
        return out
    add(str(value))
    return out


def tissue_facet(records: list[dict[str, Any]], key: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in records or []:
        if not isinstance(item, dict):
            continue
        value = item.get(key)
        if value is None:
            continue
        text = canonicalize_facet_value(str(value))
        fold = text.casefold()
        if text and fold not in seen:
            seen.add(fold)
            out.append(text)
    return out


def parse_published_at(value: Any) -> int:
    if not value:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return 0
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def empty_tissue_hierarchy() -> dict[str, list[str]]:
    return {f"tissue_hierarchy.lvl{i}": [] for i in range(TISSUE_HIER_MAX_LEVELS)}


def fenix_tissue_paths(
    tissues: list[Any], ols_cache: dict[str, Any] | None
) -> list[list[str]]:
    """Build OLS hierarchy paths for Fenix tissue objects (curie-first)."""
    paths: list[list[str]] = []
    if ols_cache is None:
        return paths
    for item in tissues:
        if not isinstance(item, dict):
            continue
        curie = item.get("ontology_term_id") or item.get("top-organ-uberon")
        label = item.get("label") or item.get("top-organ-name")
        path = resolve_path(
            curie=str(curie) if curie else None,
            label=str(label) if label else None,
            cache=ols_cache,
            refresh=False,
            sleep_s=0,
        )
        # Fallback: top-organ → tissue label when OLS misses
        if not path:
            fallback = [
                x
                for x in (
                    item.get("top-organ-name"),
                    item.get("label"),
                )
                if x
            ]
            # dedupe consecutive
            cleaned: list[str] = []
            for raw in fallback:
                text = canonicalize_facet_value(str(raw))
                if text and (not cleaned or cleaned[-1].casefold() != text.casefold()):
                    cleaned.append(text)
            path = cleaned
        if path:
            paths.append(path)
    return paths


def scp_tissue_paths(
    organs: list[str], ols_cache: dict[str, Any] | None
) -> list[list[str]]:
    """Best-effort OLS paths for SCP organ labels."""
    paths: list[list[str]] = []
    if ols_cache is None:
        return [[o] for o in organs if o]
    for organ in organs:
        path = resolve_path(
            label=organ, cache=ols_cache, refresh=False, sleep_s=0
        )
        if not path:
            path = [organ]
        paths.append(path)
    return paths


def flatten_fenix(
    raw: dict[str, Any], *, ols_cache: dict[str, Any] | None = None
) -> dict[str, Any]:
    tissues = raw.get("tissue") or []
    if not isinstance(tissues, list):
        tissues = [tissues]

    doc_id = str(raw.get("id") or raw.get("_id") or raw.get("experiment_id"))
    title = raw.get("title") or raw.get("experiment_id") or doc_id
    journal = raw.get("study_journal")
    if isinstance(journal, dict):
        journal = journal.get("label") or journal.get("long_name")
    if not journal:
        resolution = raw.get("journal_resolution") or {}
        if isinstance(resolution, dict):
            journal = resolution.get("long_name") or resolution.get("short_name")

    h5ad_url = None
    for asset in raw.get("assets") or []:
        if isinstance(asset, dict) and str(asset.get("filetype", "")).upper() == "H5AD":
            h5ad_url = asset.get("url")
            break

    organism = labels(raw.get("organism"))
    top_organ = tissue_facet(tissues, "top-organ-name")
    tissue = tissue_facet(tissues, "label")
    assay = labels(raw.get("assay"))
    disease = labels(raw.get("disease"))
    cell_type = labels(raw.get("cell_type"))
    hierarchy = paths_to_hierarchy_fields(
        fenix_tissue_paths(tissues, ols_cache),
        canonicalize=canonicalize_facet_value,
    )

    search_bits = [
        SOURCE_FENIX,
        title,
        raw.get("experiment_id"),
        raw.get("study_id"),
        raw.get("citation"),
        raw.get("search_text"),
        *organism,
        *assay,
        *disease,
        *cell_type,
        *tissue,
        *top_organ,
    ]

    doc = {
        "id": f"fenix::{doc_id}",
        "title": str(title),
        "source": SOURCE_FENIX,
        "experiment_id": str(raw.get("experiment_id") or ""),
        "study_id": str(raw.get("study_id") or ""),
        "organism": organism,
        "top_organ": top_organ,
        "tissue": tissue,
        "tissue_type": tissue_facet(tissues, "tissue_type"),
        "assay": assay,
        "disease": disease,
        "suspension_type": labels(raw.get("suspension_type")),
        "sex": labels(raw.get("sex")),
        "development_stage": labels(raw.get("development_stage")),
        "self_reported_ethnicity": labels(raw.get("self_reported_ethnicity")),
        "study_journal": canonicalize_facet_value(str(journal)) if journal else "unknown",
        "cell_type": cell_type,
        "cell_count": int(raw.get("cell_count") or raw.get("primary_cell_count") or 0),
        "feature_count": int(raw.get("feature_count") or 0),
        "published_at": parse_published_at(raw.get("published_at")),
        "explorer_url": str(raw.get("explorer_url") or ""),
        "h5ad_url": str(h5ad_url or ""),
        "search_blob": " | ".join(str(bit) for bit in search_bits if bit),
    }
    doc.update(hierarchy or empty_tissue_hierarchy())
    return doc


def flatten_scp(
    raw: dict[str, Any], *, ols_cache: dict[str, Any] | None = None
) -> dict[str, Any]:
    meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    accession = str(raw.get("accession") or "").strip()
    if not accession:
        raise ValueError("SCP study missing accession")

    organism = labels(meta.get("species"))
    organs = labels(meta.get("organ"))
    assay = labels(meta.get("library_preparation_protocol"))
    disease = labels(meta.get("disease"))
    sex = labels(meta.get("sex"))
    title = str(raw.get("name") or accession)
    study_url = str(raw.get("study_url") or "")
    explorer = (
        f"{SCP_ORIGIN}{study_url}"
        if study_url.startswith("/")
        else study_url or f"{SCP_ORIGIN}/single_cell/study/{accession}"
    )
    hierarchy = paths_to_hierarchy_fields(
        scp_tissue_paths(organs, ols_cache),
        canonicalize=canonicalize_facet_value,
    )

    search_bits = [
        SOURCE_SCP,
        "Single Cell Portal",
        title,
        accession,
        raw.get("description"),
        raw.get("study_source"),
        *organism,
        *organs,
        *assay,
        *disease,
        *sex,
    ]

    doc = {
        "id": f"scp::{accession}",
        "title": title,
        "source": SOURCE_SCP,
        "experiment_id": accession,
        "study_id": accession,
        "organism": organism,
        "top_organ": organs,  # SCP exposes organ only; reuse for top_organ facet
        "tissue": organs,
        "tissue_type": [],
        "assay": assay,
        "disease": disease,
        "suspension_type": [],
        "sex": sex,
        "development_stage": [],
        "self_reported_ethnicity": [],
        "study_journal": "unknown",
        "cell_type": [],
        "cell_count": int(raw.get("cell_count") or 0),
        "feature_count": int(raw.get("gene_count") or 0),
        "published_at": 0,
        "explorer_url": explorer,
        "h5ad_url": "",
        "search_blob": " | ".join(str(bit) for bit in search_bits if bit),
    }
    doc.update(hierarchy or empty_tissue_hierarchy())
    return doc


COLLECTION_SCHEMA: dict[str, Any] = {
    "name": COLLECTION,
    "fields": [
        {"name": "title", "type": "string"},
        {"name": "source", "type": "string", "facet": True},
        {"name": "experiment_id", "type": "string", "optional": True},
        {"name": "study_id", "type": "string", "optional": True, "facet": True},
        {"name": "organism", "type": "string[]", "facet": True, "optional": True},
        {"name": "top_organ", "type": "string[]", "facet": True, "optional": True},
        {"name": "tissue", "type": "string[]", "facet": True, "optional": True},
        {"name": "tissue_type", "type": "string[]", "facet": True, "optional": True},
        # InstantSearch HierarchicalMenu (Typesense field.lvlN convention)
        {"name": "tissue_hierarchy.lvl0", "type": "string[]", "facet": True, "optional": True},
        {"name": "tissue_hierarchy.lvl1", "type": "string[]", "facet": True, "optional": True},
        {"name": "tissue_hierarchy.lvl2", "type": "string[]", "facet": True, "optional": True},
        {"name": "tissue_hierarchy.lvl3", "type": "string[]", "facet": True, "optional": True},
        {"name": "tissue_hierarchy.lvl4", "type": "string[]", "facet": True, "optional": True},
        {"name": "tissue_hierarchy.lvl5", "type": "string[]", "facet": True, "optional": True},
        {"name": "assay", "type": "string[]", "facet": True, "optional": True},
        {"name": "disease", "type": "string[]", "facet": True, "optional": True},
        {"name": "suspension_type", "type": "string[]", "facet": True, "optional": True},
        {"name": "sex", "type": "string[]", "facet": True, "optional": True},
        {"name": "development_stage", "type": "string[]", "facet": True, "optional": True},
        {
            "name": "self_reported_ethnicity",
            "type": "string[]",
            "facet": True,
            "optional": True,
        },
        {"name": "study_journal", "type": "string", "facet": True, "optional": True},
        {"name": "cell_type", "type": "string[]", "facet": True, "optional": True},
        {"name": "cell_count", "type": "int32"},
        {"name": "feature_count", "type": "int32", "optional": True},
        {"name": "published_at", "type": "int64", "optional": True},
        {"name": "explorer_url", "type": "string", "optional": True, "index": False},
        {"name": "h5ad_url", "type": "string", "optional": True, "index": False},
        {"name": "search_blob", "type": "string", "optional": True},
    ],
    "default_sorting_field": "cell_count",
    "token_separators": ["_", "-", "/"],
}


def client_from_env() -> typesense.Client:
    return typesense.Client(
        {
            "nodes": [
                {
                    "host": os.getenv("TYPESENSE_HOST", "localhost"),
                    "port": os.getenv("TYPESENSE_PORT", "8108"),
                    "protocol": os.getenv("TYPESENSE_PROTOCOL", "http"),
                }
            ],
            "api_key": os.getenv("TYPESENSE_API_KEY", "bh2026-typesense-admin-key"),
            "connection_timeout_seconds": 30,
        }
    )


def wait_for_typesense(client: typesense.Client, attempts: int = 30) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            health = client.operations.is_healthy()
            if health is True or health.get("ok") is True:
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"Typesense not healthy after {attempts}s: {last_error}")


def recreate_collection(client: typesense.Client) -> None:
    try:
        client.collections[COLLECTION].delete()
        print(f"Deleted existing collection '{COLLECTION}'")
    except ObjectNotFound:
        pass
    client.collections.create(COLLECTION_SCHEMA)
    print(f"Created collection '{COLLECTION}'")


def ensure_collection(client: typesense.Client, *, recreate: bool) -> None:
    if recreate:
        recreate_collection(client)
        return
    try:
        client.collections[COLLECTION].retrieve()
        print(f"Using existing collection '{COLLECTION}'")
    except ObjectNotFound:
        try:
            client.collections.create(COLLECTION_SCHEMA)
            print(f"Created collection '{COLLECTION}'")
        except ObjectAlreadyExists:
            pass


def load_fenix(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "data" in payload:
        records = payload["data"]
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError(f"Unexpected Fenix JSON shape in {path}")
    if not isinstance(records, list):
        raise ValueError("Fenix `data` must be a list")
    return records


def load_scp(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "studies" in payload:
        records = payload["studies"]
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError(f"Unexpected SCP JSON shape in {path}")
    if not isinstance(records, list):
        raise ValueError("SCP `studies` must be a list")
    return records


def batched(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def import_docs(
    client: typesense.Client, docs: list[dict[str, Any]], batch_size: int
) -> tuple[int, int]:
    imported = 0
    failed = 0
    for batch in batched(docs, batch_size):
        result = client.collections[COLLECTION].documents.import_(
            batch, {"action": "upsert"}
        )
        if isinstance(result, str):
            rows = [json.loads(line) for line in result.splitlines() if line.strip()]
        else:
            rows = list(result)
        for row in rows:
            if row.get("success"):
                imported += 1
            else:
                failed += 1
                print(f"Import error: {row}", file=sys.stderr)
    return imported, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fenix-json", type=Path, default=DEFAULT_FENIX_JSON)
    parser.add_argument("--scp-json", type=Path, default=DEFAULT_SCP_JSON)
    parser.add_argument(
        "--skip-fenix", action="store_true", help="Do not index Fenix experiments"
    )
    parser.add_argument(
        "--skip-scp", action="store_true", help="Do not index Single Cell Portal studies"
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the Typesense collection before indexing",
    )
    parser.add_argument(
        "--skip-ols",
        action="store_true",
        help="Skip OLS tissue hierarchy enrichment (hierarchy fields stay empty)",
    )
    parser.add_argument(
        "--refresh-ols",
        action="store_true",
        help="Re-query OLS even when cache entries exist",
    )
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args(argv)

    docs: list[dict[str, Any]] = []
    counts = {SOURCE_FENIX: 0, SOURCE_SCP: 0}
    ols_cache: dict[str, Any] | None = None

    fenix_records: list[dict[str, Any]] = []
    scp_records: list[dict[str, Any]] = []

    if not args.skip_fenix:
        if not args.fenix_json.is_file():
            print(f"Missing Fenix JSON: {args.fenix_json}", file=sys.stderr)
            return 1
        fenix_records = load_fenix(args.fenix_json)

    if not args.skip_scp:
        if not args.scp_json.is_file():
            print(f"Missing SCP JSON: {args.scp_json}", file=sys.stderr)
            print(
                "Run: python3 WP1/single_cell_portal/download_studies.py --summarize",
                file=sys.stderr,
            )
            return 1
        scp_records = load_scp(args.scp_json)

    if not args.skip_ols and (fenix_records or scp_records):
        print("Warming OLS tissue hierarchy cache…")
        curies: list[str] = []
        for exp in fenix_records:
            for tissue in exp.get("tissue") or []:
                if isinstance(tissue, dict):
                    if tissue.get("ontology_term_id"):
                        curies.append(str(tissue["ontology_term_id"]))
                    if tissue.get("top-organ-uberon"):
                        curies.append(str(tissue["top-organ-uberon"]))
        warm_cache_for_curies(
            curies, refresh=args.refresh_ols, sleep_s=0.05 if args.refresh_ols else 0.02
        )
        organ_labels: list[str] = []
        for study in scp_records:
            meta = study.get("metadata") if isinstance(study, dict) else {}
            for organ in (meta or {}).get("organ") or []:
                organ_labels.append(str(organ))
        if organ_labels:
            warm_cache_for_labels(
                organ_labels,
                refresh=args.refresh_ols,
                sleep_s=0.05 if args.refresh_ols else 0.02,
            )
        ols_cache = load_ols_cache()
        print(
            f"OLS cache loaded "
            f"({len(ols_cache.get('by_curie', {}))} curies, "
            f"{len(ols_cache.get('by_label', {}))} labels)"
        )

    if fenix_records:
        fenix_docs = [
            flatten_fenix(record, ols_cache=ols_cache) for record in fenix_records
        ]
        docs.extend(fenix_docs)
        counts[SOURCE_FENIX] = len(fenix_docs)
        print(f"Prepared {len(fenix_docs)} Fenix docs from {args.fenix_json}")

    if scp_records:
        scp_docs = [
            flatten_scp(record, ols_cache=ols_cache) for record in scp_records
        ]
        docs.extend(scp_docs)
        counts[SOURCE_SCP] = len(scp_docs)
        print(f"Prepared {len(scp_docs)} SCP docs from {args.scp_json}")

    if not docs:
        print("Nothing to index.", file=sys.stderr)
        return 1

    client = client_from_env()
    wait_for_typesense(client)
    ensure_collection(client, recreate=args.recreate)

    print(f"Indexing {len(docs)} documents…")
    imported, failed = import_docs(client, docs, args.batch_size)
    print(f"Done. imported={imported} failed={failed}")
    print(
        "Counts by source: "
        + ", ".join(f"{name}={counts[name]}" for name in (SOURCE_FENIX, SOURCE_SCP))
    )
    print("Facet fields:", ", ".join(FACET_FIELDS))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
