#!/usr/bin/env python3
"""Warm / refresh the OLS cell-type (CL) hierarchy cache used by the indexer.

Examples:

    # Resolve all Fenix CL cell_type IDs into ols_cache/cl_paths.json
    python enrich_cell_type_hierarchy.py

    # Force re-fetch from OLS (ignore cached paths)
    python enrich_cell_type_hierarchy.py --refresh

Then re-index:

    python index_experiments.py --recreate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ols_cell_type import (
    CACHE_FILE,
    warm_cache_for_curies,
)

WP1 = Path(__file__).resolve().parents[2]


def fenix_cell_type_curies(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("data") if isinstance(payload, dict) else payload
    curies: list[str] = []
    for exp in records or []:
        for cell in exp.get("cell_type") or []:
            if isinstance(cell, dict) and cell.get("ontology_term_id"):
                curies.append(str(cell["ontology_term_id"]))
    return curies


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fenix-json",
        type=Path,
        default=WP1 / "fenix" / "experiments.json",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-query OLS even when a cache entry exists",
    )
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args(argv)

    if not args.fenix_json.is_file():
        print(f"Missing Fenix JSON: {args.fenix_json}", file=sys.stderr)
        return 1

    curies = fenix_cell_type_curies(args.fenix_json)
    print(
        f"Warming OLS CL cache for {len(set(curies))} unique Fenix cell_type curies "
        f"→ {CACHE_FILE}"
    )
    warm_cache_for_curies(curies, refresh=args.refresh, sleep_s=args.sleep)
    print(f"Done. Cache at {CACHE_FILE}")
    print("Re-index with: python index_experiments.py --recreate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
