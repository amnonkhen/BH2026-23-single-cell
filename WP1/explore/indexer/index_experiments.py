#!/usr/bin/env python3
"""Flatten WP1/fenix/experiments.json into a Typesense collection with facets."""

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

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.example", override=False)

COLLECTION = os.getenv("TYPESENSE_COLLECTION", "experiments")
DEFAULT_JSON = Path(
    os.getenv("EXPERIMENTS_JSON", str(ROOT.parent / "fenix" / "experiments.json"))
)

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


def labels(value: Any, extra_keys: Iterable[str] = ()) -> list[str]:
    """Extract unique label strings from ontology objects, strings, or lists."""
    out: list[str] = []
    seen: set[str] = set()

    def add(item: str | None) -> None:
        if not item:
            return
        text = str(item).strip()
        if not text or text in seen:
            return
        seen.add(text)
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
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
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


def flatten_experiment(raw: dict[str, Any]) -> dict[str, Any]:
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

    search_bits = [
        title,
        raw.get("experiment_id"),
        raw.get("study_id"),
        raw.get("citation"),
        raw.get("search_text"),
    ]
    for field in (
        "organism",
        "assay",
        "disease",
        "cell_type",
        "development_stage",
        "sex",
    ):
        search_bits.extend(labels(raw.get(field)))
    search_bits.extend(tissue_facet(tissues, "label"))
    search_bits.extend(tissue_facet(tissues, "top-organ-name"))

    cell_count = int(raw.get("cell_count") or raw.get("primary_cell_count") or 0)
    feature_count = int(raw.get("feature_count") or 0)

    return {
        "id": doc_id,
        "title": str(title),
        "experiment_id": str(raw.get("experiment_id") or ""),
        "study_id": str(raw.get("study_id") or ""),
        "organism": labels(raw.get("organism")),
        "top_organ": tissue_facet(tissues, "top-organ-name"),
        "tissue": tissue_facet(tissues, "label"),
        "tissue_type": tissue_facet(tissues, "tissue_type"),
        "assay": labels(raw.get("assay")),
        "disease": labels(raw.get("disease")),
        "suspension_type": labels(raw.get("suspension_type")),
        "sex": labels(raw.get("sex")),
        "development_stage": labels(raw.get("development_stage")),
        "self_reported_ethnicity": labels(raw.get("self_reported_ethnicity")),
        "study_journal": str(journal or "") or "unknown",
        "cell_type": labels(raw.get("cell_type")),
        "cell_count": cell_count,
        "feature_count": feature_count,
        "published_at": parse_published_at(raw.get("published_at")),
        "explorer_url": str(raw.get("explorer_url") or ""),
        "h5ad_url": str(h5ad_url or ""),
        "search_blob": " | ".join(str(bit) for bit in search_bits if bit),
    }


COLLECTION_SCHEMA: dict[str, Any] = {
    "name": COLLECTION,
    "fields": [
        {"name": "title", "type": "string"},
        {"name": "experiment_id", "type": "string", "optional": True},
        {"name": "study_id", "type": "string", "optional": True, "facet": True},
        {"name": "organism", "type": "string[]", "facet": True},
        {"name": "top_organ", "type": "string[]", "facet": True},
        {"name": "tissue", "type": "string[]", "facet": True},
        {"name": "tissue_type", "type": "string[]", "facet": True},
        {"name": "assay", "type": "string[]", "facet": True},
        {"name": "disease", "type": "string[]", "facet": True},
        {"name": "suspension_type", "type": "string[]", "facet": True},
        {"name": "sex", "type": "string[]", "facet": True},
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
        except Exception as exc:  # noqa: BLE001 — retry until Typesense is up
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


def load_experiments(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "data" in payload:
        records = payload["data"]
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError(f"Unexpected JSON shape in {path}")
    if not isinstance(records, list):
        raise ValueError("`data` must be a list of experiments")
    return records


def batched(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        type=Path,
        default=DEFAULT_JSON,
        help="Path to experiments.json (default: WP1/fenix/experiments.json)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the Typesense collection before indexing",
    )
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args(argv)

    if not args.json.is_file():
        print(f"Missing experiments JSON: {args.json}", file=sys.stderr)
        print(
            "Checkout the fenix catalog branch or run WP1/fenix/download_experiments.py",
            file=sys.stderr,
        )
        return 1

    client = client_from_env()
    wait_for_typesense(client)
    ensure_collection(client, recreate=args.recreate)

    raw_records = load_experiments(args.json)
    docs = [flatten_experiment(record) for record in raw_records]
    print(f"Indexing {len(docs)} experiments from {args.json}")

    imported = 0
    failed = 0
    for batch in batched(docs, args.batch_size):
        result = client.collections[COLLECTION].documents.import_(
            batch, {"action": "upsert"}
        )
        # typesense-python may return list[dict] or newline JSON
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

    print(f"Done. imported={imported} failed={failed}")
    print("Facet fields:", ", ".join(FACET_FIELDS))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
