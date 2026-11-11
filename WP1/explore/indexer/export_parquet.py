#!/usr/bin/env python3
"""Export flattened experiment catalogs to Parquet for the browser UI.

Built-in source:
  - Fenix (`--fenix-json`) → `source=scfair`

Additional partner JSON files (new-source ingest schema):

  python export_parquet.py --json my_partner=/path/to/datasets.json

Re-run this script whenever catalogs change, then refresh the Vite UI
(hard-refresh the browser so `/experiments.parquet` reloads).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from catalog import (
    DEFAULT_FENIX_JSON,
    flatten_fenix,
    flatten_partner,
    load_fenix,
    load_partner,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "ui" / "public" / "experiments.parquet"

LIST_FIELDS = [
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
    "cell_type",
]


def parse_source_json(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            f"--json expects SOURCE=PATH, got {value!r}"
        )
    source, path_str = value.split("=", 1)
    source = source.strip()
    path = Path(path_str.strip()).expanduser()
    if not source:
        raise argparse.ArgumentTypeError(f"empty source name in {value!r}")
    if not path_str.strip():
        raise argparse.ArgumentTypeError(f"empty path in {value!r}")
    return source, path


def collect_docs(
    *,
    fenix_json: Path,
    skip_fenix: bool,
    extras: list[tuple[str, Path]],
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []

    if not skip_fenix:
        if not fenix_json.is_file():
            raise FileNotFoundError(f"Missing Fenix JSON: {fenix_json}")
        fenix_records = load_fenix(fenix_json)
        fenix_docs = [flatten_fenix(record) for record in fenix_records]
        docs.extend(fenix_docs)
        print(f"Prepared {len(fenix_docs)} Fenix docs from {fenix_json}")

    for source, path in extras:
        if not path.is_file():
            raise FileNotFoundError(f"Missing partner JSON for {source}: {path}")
        records = load_partner(path)
        partner_docs = [flatten_partner(record, source=source) for record in records]
        docs.extend(partner_docs)
        print(f"Prepared {len(partner_docs)} docs for source={source}")

    return docs


def docs_to_table(docs: list[dict[str, Any]]) -> pa.Table:
    if not docs:
        raise ValueError("No documents to export")

    columns: dict[str, list[Any]] = {key: [] for key in docs[0]}
    for doc in docs:
        for key in columns:
            value = doc.get(key)
            if key in LIST_FIELDS:
                if value is None:
                    columns[key].append([])
                elif isinstance(value, list):
                    columns[key].append([str(v) for v in value if v is not None])
                else:
                    columns[key].append([str(value)])
            else:
                columns[key].append(value)

    arrays: dict[str, pa.Array] = {}
    for key, values in columns.items():
        if key in LIST_FIELDS:
            arrays[key] = pa.array(values, type=pa.list_(pa.string()))
        elif key in {"cell_count", "feature_count", "published_at"}:
            arrays[key] = pa.array(values, type=pa.int64())
        else:
            arrays[key] = pa.array([None if v is None else str(v) for v in values])
    return pa.table(arrays)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fenix-json", type=Path, default=DEFAULT_FENIX_JSON)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--skip-fenix", action="store_true")
    parser.add_argument(
        "--json",
        dest="extra_json",
        action="append",
        default=[],
        type=parse_source_json,
        metavar="SOURCE=PATH",
        help="Extra partner catalog (repeatable). Example: --json partner=./data.json",
    )
    args = parser.parse_args(argv)

    try:
        docs = collect_docs(
            fenix_json=args.fenix_json,
            skip_fenix=args.skip_fenix,
            extras=args.extra_json,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not docs:
        print("Nothing to export.", file=sys.stderr)
        return 1

    table = docs_to_table(docs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, args.out, compression="zstd")
    counts = Counter(str(d.get("source") or "unknown") for d in docs)
    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(
        f"Wrote {len(docs)} rows "
        f"({', '.join(f'{k}={v}' for k, v in sorted(counts.items()))}) "
        f"→ {args.out} ({size_mb:.2f} MiB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
