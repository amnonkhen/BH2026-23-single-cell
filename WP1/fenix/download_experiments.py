#!/usr/bin/env python3
"""Download CELLxGENE / Fenix experiment metadata from the EBI wwwdev API.

Default output: experiments.json next to this script.
Refresh with:

    python3 WP1/fenix/download_experiments.py

Optional flags:

    python3 WP1/fenix/download_experiments.py --out /path/to/file.json
    python3 WP1/fenix/download_experiments.py --summarize
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

DEFAULT_URL = (
    "https://wwwdev.ebi.ac.uk/fenix/api/experiments"
    "?page=1&perPage=10000&sortField=title&sortOrder=ASC&include_journals=true"
)


def download(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset))


def summarize(payload: dict) -> dict:
    experiments = payload.get("data") or []
    summary: dict = {
        "total": payload.get("total", len(experiments)),
        "n_records": len(experiments),
        "top_level_keys": sorted(payload.keys()),
        "record_fields": sorted({k for e in experiments for k in e.keys()}),
        "facets": {},
    }

    def collect(field: str, *, nested: str | None = None) -> Counter:
        counts: Counter = Counter()
        for exp in experiments:
            values = exp.get(field)
            if values is None:
                continue
            if nested is None and not isinstance(values, list):
                if values != "":
                    counts[str(values)] += 1
                continue
            if not isinstance(values, list):
                continue
            seen = set()
            for item in values:
                if nested is None:
                    key = str(item)
                elif isinstance(item, dict) and item.get(nested) is not None:
                    key = str(item[nested])
                else:
                    continue
                if key not in seen:
                    counts[key] += 1
                    seen.add(key)
        return counts

    facet_specs = [
        ("organism.label", "organism", "label"),
        ("tissue.label", "tissue", "label"),
        ("tissue.top-organ-name", "tissue", "top-organ-name"),
        ("tissue.tissue_type", "tissue", "tissue_type"),
        ("assay.label", "assay", "label"),
        ("disease.label", "disease", "label"),
        ("cell_type.label", "cell_type", "label"),
        ("development_stage.label", "development_stage", "label"),
        ("sex.label", "sex", "label"),
        ("self_reported_ethnicity.label", "self_reported_ethnicity", "label"),
        ("suspension_type", "suspension_type", None),
        ("study_journal", "study_journal", None),
        ("schema_version", "schema_version", None),
    ]

    for name, field, nested in facet_specs:
        counts = collect(field, nested=nested)
        summary["facets"][name] = {
            "unique": len(counts),
            "top": counts.most_common(20),
        }

    return summary


def write_sample(payload: dict, path: Path, n: int = 2) -> None:
    sample = {
        "data": (payload.get("data") or [])[:n],
        "total": payload.get("total"),
        "_note": f"First {n} experiments only; full file is experiments.json",
    }
    path.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="Fenix experiments API URL")
    parser.add_argument(
        "--out",
        type=Path,
        default=here / "experiments.json",
        help="Where to write the full JSON payload",
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=here / "experiments.sample.json",
        help="Where to write a small sample JSON (use '' to skip)",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=here / "experiments.schema-summary.json",
        help="Where to write a facet/cardinality summary (use '' to skip)",
    )
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Print a short facet summary to stdout after download",
    )
    args = parser.parse_args(argv)

    print(f"Fetching {args.url}", file=sys.stderr)
    try:
        payload = download(args.url)
    except urllib.error.URLError as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1

    experiments = payload.get("data") or []
    total = payload.get("total", len(experiments))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(
        f"Wrote {args.out} ({size_mb:.2f} MiB; {len(experiments)} records, API total={total})",
        file=sys.stderr,
    )

    if str(args.sample):
        write_sample(payload, args.sample)
        print(f"Wrote {args.sample}", file=sys.stderr)

    if str(args.summary):
        summary = summarize(payload)
        args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.summary}", file=sys.stderr)
        if args.summarize:
            print(json.dumps({k: v["unique"] for k, v in summary["facets"].items()}, indent=2))

    if len(experiments) < total:
        print(
            f"Warning: API reports total={total} but this page returned {len(experiments)}. "
            "Increase perPage or paginate.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
