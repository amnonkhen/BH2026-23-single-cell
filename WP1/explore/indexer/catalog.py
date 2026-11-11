#!/usr/bin/env python3
"""Flatten experiment catalogs into explore documents (Parquet export).

Every document includes a faceted `source` field (e.g. scfair or a partner
source name passed to export_parquet.py --json SOURCE=PATH).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
WP1 = ROOT.parent
# Catalog JSON still lives under WP1/fenix/; explore `source` facet is scfair.
DEFAULT_CATALOG_JSON = WP1 / "fenix" / "experiments.json"
DEFAULT_FENIX_JSON = DEFAULT_CATALOG_JSON  # alias for older scripts

SOURCE_SCFAIR = "scfair"
SOURCE_FENIX = SOURCE_SCFAIR  # backwards-compatible alias


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


def flatten_fenix(raw: dict[str, Any]) -> dict[str, Any]:
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
    raw_cell_types = raw.get("cell_type") or []
    if not isinstance(raw_cell_types, list):
        raw_cell_types = [raw_cell_types]
    cell_type = labels(raw_cell_types)

    search_bits = [
        SOURCE_SCFAIR,
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

    return {
        "id": f"scfair::{doc_id}",
        "title": str(title),
        "source": SOURCE_SCFAIR,
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


def load_partner(path: Path) -> list[dict[str, Any]]:
    """Load partner catalogs: `{datasets:[…]}`, `{data:[…]}`, or a bare list."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("datasets"), list):
            records = payload["datasets"]
        elif isinstance(payload.get("data"), list):
            records = payload["data"]
        else:
            raise ValueError(
                f"Unexpected partner JSON shape in {path} "
                "(expected datasets/data list or a bare array)"
            )
    else:
        raise ValueError(f"Unexpected partner JSON shape in {path}")
    return records


def flatten_partner(raw: dict[str, Any], *, source: str) -> dict[str, Any]:
    """Flatten a partner record (same Term shape as the new-source ingest schema)."""
    source = str(source or raw.get("source") or "partner").strip() or "partner"
    tissues = raw.get("tissue") or []
    if not isinstance(tissues, list):
        tissues = [tissues]
    raw_cell_types = raw.get("cell_type") or []
    if not isinstance(raw_cell_types, list):
        raw_cell_types = [raw_cell_types]

    doc_id = str(raw.get("id") or raw.get("experiment_id") or "").strip()
    if not doc_id:
        raise ValueError("Partner dataset missing id/experiment_id")
    title = raw.get("title") or raw.get("experiment_id") or doc_id
    journal = raw.get("study_journal")
    if isinstance(journal, dict):
        journal = journal.get("label") or journal.get("long_name")

    h5ad_url = raw.get("h5ad_url")
    if not h5ad_url:
        for asset in raw.get("assets") or []:
            if isinstance(asset, dict) and str(asset.get("filetype", "")).upper() == "H5AD":
                h5ad_url = asset.get("url")
                break

    organism = labels(raw.get("organism"))
    top_organ = tissue_facet(tissues, "top-organ-name")
    tissue = tissue_facet(tissues, "label")
    assay = labels(raw.get("assay"))
    disease = labels(raw.get("disease"))
    cell_type = labels(raw_cell_types)

    search_bits = [
        source,
        title,
        raw.get("experiment_id"),
        raw.get("study_id"),
        raw.get("citation"),
        *organism,
        *assay,
        *disease,
        *cell_type,
        *tissue,
        *top_organ,
    ]
    return {
        "id": f"{source}::{doc_id}",
        "title": str(title),
        "source": source,
        "experiment_id": str(raw.get("experiment_id") or doc_id),
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
