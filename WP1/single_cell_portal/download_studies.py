#!/usr/bin/env python3
"""Download Single Cell Portal study metadata (Broad Institute search API).

Caches the full study list next to this script as studies.json.

    python3 WP1/single_cell_portal/download_studies.py
    python3 WP1/single_cell_portal/download_studies.py --summarize
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

DEFAULT_BASE = (
    "https://singlecell.broadinstitute.org/single_cell/api/v1/search?type=study"
)
SCP_ORIGIN = "https://singlecell.broadinstitute.org"


def fetch_page(base_url: str, page: int) -> dict:
    parsed = urllib.parse.urlparse(base_url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["type"] = query.get("type") or "study"
    query["page"] = str(page)
    url = urllib.parse.urlunparse(
        parsed._replace(query=urllib.parse.urlencode(query))
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "BH2026-23-single-cell/explore-indexer",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset))


def download_all(base_url: str, *, sleep_s: float = 0.05) -> dict:
    first = fetch_page(base_url, 1)
    total_pages = int(first.get("total_pages") or 1)
    total_studies = int(first.get("total_studies") or 0)
    studies = list(first.get("studies") or [])
    accessions = list(first.get("matching_accessions") or [])

    print(f"Page 1/{total_pages}: {len(studies)} studies (API total={total_studies})")
    for page in range(2, total_pages + 1):
        if sleep_s:
            time.sleep(sleep_s)
        payload = fetch_page(base_url, page)
        batch = payload.get("studies") or []
        studies.extend(batch)
        print(f"Page {page}/{total_pages}: +{len(batch)} (running {len(studies)})")

    return {
        "source": "single_cell_portal",
        "api_url": base_url,
        "total_studies": total_studies,
        "total_pages": total_pages,
        "n_records": len(studies),
        "matching_accessions": accessions,
        "studies": studies,
    }


def summarize(payload: dict) -> dict:
    studies = payload.get("studies") or []
    summary: dict = {
        "total_studies": payload.get("total_studies", len(studies)),
        "n_records": len(studies),
        "top_level_keys": sorted(payload.keys()),
        "record_fields": sorted({k for s in studies for k in s.keys()}),
        "metadata_fields": sorted(
            {
                k
                for s in studies
                for k in (s.get("metadata") or {}).keys()
                if isinstance(s.get("metadata"), dict)
            }
        ),
        "facets": {},
    }

    def collect_meta(field: str) -> Counter:
        counts: Counter = Counter()
        for study in studies:
            meta = study.get("metadata") or {}
            values = meta.get(field)
            if not isinstance(values, list):
                continue
            seen = set()
            for item in values:
                key = str(item).strip()
                if key and key not in seen:
                    counts[key] += 1
                    seen.add(key)
        return counts

    for field in (
        "species",
        "organ",
        "disease",
        "sex",
        "library_preparation_protocol",
    ):
        counts = collect_meta(field)
        summary["facets"][f"metadata.{field}"] = {
            "unique": len(counts),
            "top": counts.most_common(20),
        }

    public = Counter(str(bool(s.get("public"))) for s in studies)
    summary["facets"]["public"] = {"unique": len(public), "top": public.most_common()}
    return summary


def write_sample(payload: dict, path: Path, n: int = 2) -> None:
    studies = payload.get("studies") or []
    sample = {
        "source": payload.get("source"),
        "total_studies": payload.get("total_studies"),
        "n_records": min(n, len(studies)),
        "studies": studies[:n],
    }
    path.write_text(json.dumps(sample, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_BASE, help="Search API base URL")
    parser.add_argument(
        "--out",
        type=Path,
        default=here / "studies.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Also write studies.schema-summary.json and studies.sample.json",
    )
    parser.add_argument("--sleep", type=float, default=0.05, help="Delay between pages")
    args = parser.parse_args(argv)

    try:
        payload = download_all(args.url, sleep_s=args.sleep)
    except urllib.error.URLError as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.out} ({payload['n_records']} studies, "
        f"API total_studies={payload['total_studies']})"
    )

    if args.summarize or True:
        summary = summarize(payload)
        summary_path = args.out.with_name("studies.schema-summary.json")
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        sample_path = args.out.with_name("studies.sample.json")
        write_sample(payload, sample_path)
        print(f"Wrote {summary_path} and {sample_path}")

    if payload["n_records"] != payload["total_studies"]:
        print(
            f"Warning: n_records={payload['n_records']} != total_studies={payload['total_studies']}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
