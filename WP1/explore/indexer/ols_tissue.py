#!/usr/bin/env python3
"""OLS (EBI) tissue hierarchy helpers with on-disk cache.

Resolves UBERON curies (and best-effort label lookups) to hierarchical
label paths used as InstantSearch `tissue_hierarchy.lvlN` values.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CACHE_DIR = Path(__file__).resolve().parent / "ols_cache"
CACHE_FILE = CACHE_DIR / "uberon_paths.json"
OLS_BASE = "https://www.ebi.ac.uk/ols4/api"
HIER_SEP = " > "
MAX_LEVELS = 6

# Drop ultra-generic upper ontology / UBERON roots from browse paths.
# Keep this aggressive so HierarchicalMenu lvl0 shows real organs/tissues,
# not abstract parents like "Organ" / "Organ Part".
SKIP_LABELS = {
    "anatomical entity",
    "material anatomical entity",
    "anatomical structure",
    "multicellular anatomical structure",
    "material entity",
    "entity",
    "continuant",
    "independent continuant",
    "occurrent",
    "specifically dependent continuant",
    "organ",
    "organ part",
    "tissue",
    "multi-tissue structure",
    "gross anatomical part",
    "anatomical system",
    "immaterial anatomical entity",
    "anatomical cluster",
    "anatomical group",
    "disconnected anatomical group",
    "organism subdivision",
    "structure with developmental contribution from neural crest",
}


def trim_generic_path(path: list[str]) -> list[str]:
    """Strip leading generic UBERON parents from a cached/fetched path."""
    cleaned = [str(x).strip() for x in path if str(x).strip()]
    while cleaned and cleaned[0].casefold() in SKIP_LABELS:
        cleaned = cleaned[1:]
    # Also drop any remaining generic-only labels that aren't useful leaves.
    return [
        label
        for label in cleaned
        if label.casefold() not in SKIP_LABELS
    ]


def _double_encode_iri(iri: str) -> str:
    return urllib.parse.quote(urllib.parse.quote(iri, safe=""), safe="")


def curie_to_iri(curie: str) -> str | None:
    text = str(curie).strip()
    if not text:
        return None
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if ":" not in text:
        return None
    ns, local = text.split(":", 1)
    ns = ns.strip()
    local = local.strip().replace(":", "_")
    if not ns or not local:
        return None
    return f"http://purl.obolibrary.org/obo/{ns}_{local}"


def load_cache(path: Path = CACHE_FILE) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "by_curie": {}, "by_label": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "by_curie": {}, "by_label": {}}
    data.setdefault("by_curie", {})
    data.setdefault("by_label", {})
    return data


def save_cache(cache: dict[str, Any], path: Path = CACHE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _http_get_json(url: str, timeout: int = 60) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "BH2026-23-explore-ols-tissue/0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset))


def _path_from_jstree(nodes: list[dict[str, Any]], curie: str) -> list[str]:
    ns, num = curie.split(":", 1)
    suffix = f"{ns}_{num}"
    targets = [n for n in nodes if (n.get("iri") or "").endswith(suffix)]
    if not targets:
        return []
    target = max(targets, key=lambda n: len(n.get("id") or ""))
    by_id = {n["id"]: n for n in nodes if n.get("id")}
    chain: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = target
    while cur:
        chain.append(cur)
        pid = cur.get("parent")
        if not pid or pid == "#":
            break
        cur = by_id.get(pid)
    chain.reverse()

    labels: list[str] = []
    for node in chain:
        iri = node.get("iri") or ""
        if "UBERON_" not in iri:
            continue
        label = str(node.get("text") or "").strip()
        if not label or label.lower() in SKIP_LABELS:
            continue
        if labels and labels[-1].casefold() == label.casefold():
            continue
        labels.append(label)
    return labels


def fetch_uberon_path(curie: str) -> list[str]:
    """Return root→leaf UBERON labels for a curie (may be empty on failure)."""
    iri = curie_to_iri(curie)
    if not iri:
        return []
    enc = _double_encode_iri(iri)
    url = (
        f"{OLS_BASE}/ontologies/uberon/terms/{enc}/jstree"
        f"?viewMode=all&siblings=false"
    )
    try:
        nodes = _http_get_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []
    if not isinstance(nodes, list):
        return []
    return _path_from_jstree(nodes, curie)


def search_uberon_curie_by_label(label: str) -> str | None:
    """Best-effort exact label → UBERON curie via OLS search."""
    q = str(label).strip()
    if not q:
        return None
    params = urllib.parse.urlencode(
        {
            "q": q,
            "ontology": "uberon",
            "exact": "true",
            "rows": "5",
            "queryFields": "label,synonym",
        }
    )
    url = f"{OLS_BASE}/search?{params}"
    try:
        payload = _http_get_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    docs = (payload or {}).get("response", {}).get("docs") or []
    for doc in docs:
        obo = doc.get("obo_id") or doc.get("short_form")
        if isinstance(obo, str) and obo.upper().startswith("UBERON:"):
            return obo.replace("_", ":", 1) if obo.startswith("UBERON_") else obo
        short = str(doc.get("short_form") or "")
        if short.startswith("UBERON_"):
            return short.replace("_", ":", 1)
    return None


def resolve_path(
    *,
    curie: str | None = None,
    label: str | None = None,
    cache: dict[str, Any] | None = None,
    refresh: bool = False,
    sleep_s: float = 0.05,
) -> list[str]:
    """Resolve a hierarchy path, using cache unless refresh=True."""
    store = cache if cache is not None else load_cache()
    by_curie: dict[str, Any] = store.setdefault("by_curie", {})
    by_label: dict[str, Any] = store.setdefault("by_label", {})

    resolved_curie = None
    if curie:
        resolved_curie = str(curie).strip()
    elif label:
        key = str(label).strip().casefold()
        hit = by_label.get(key)
        if hit and not refresh:
            if hit.get("curie"):
                resolved_curie = hit["curie"]
            elif isinstance(hit.get("path"), list):
                return list(hit["path"])
        if not resolved_curie:
            if sleep_s:
                time.sleep(sleep_s)
            resolved_curie = search_uberon_curie_by_label(label)
            by_label[key] = {
                "label": label,
                "curie": resolved_curie,
                "path": None,
            }

    if not resolved_curie:
        return []

    cached = by_curie.get(resolved_curie)
    if cached and isinstance(cached.get("path"), list) and not refresh:
        path = list(cached["path"])
    else:
        if sleep_s:
            time.sleep(sleep_s)
        path = fetch_uberon_path(resolved_curie)
        by_curie[resolved_curie] = {
            "curie": resolved_curie,
            "path": path,
            "label": label,
        }

    path = trim_generic_path(path)

    if label:
        by_label[str(label).strip().casefold()] = {
            "label": label,
            "curie": resolved_curie,
            "path": path,
        }
    return path


def paths_to_hierarchy_fields(
    paths: list[list[str]],
    *,
    max_levels: int = MAX_LEVELS,
    separator: str = HIER_SEP,
    canonicalize=None,
) -> dict[str, list[str]]:
    """Convert label paths into tissue_hierarchy.lvlN array fields (Algolia-style)."""
    levels: dict[str, list[str]] = {
        f"tissue_hierarchy.lvl{i}": [] for i in range(max_levels)
    }
    seen: dict[str, set[str]] = {k: set() for k in levels}

    for path in paths:
        cleaned: list[str] = []
        for raw in trim_generic_path(path):
            label = str(raw).strip()
            if not label:
                continue
            if canonicalize:
                label = canonicalize(label)
            if label.casefold() in SKIP_LABELS:
                continue
            if cleaned and cleaned[-1].casefold() == label.casefold():
                continue
            cleaned.append(label)
        if not cleaned:
            continue
        # Ensure leaf present; trim to max_levels from the *leaf* side if too deep
        if len(cleaned) > max_levels:
            cleaned = cleaned[-max_levels:]
        for depth in range(len(cleaned)):
            key = f"tissue_hierarchy.lvl{depth}"
            value = separator.join(cleaned[: depth + 1])
            fold = value.casefold()
            if fold not in seen[key]:
                seen[key].add(fold)
                levels[key].append(value)
    # Drop empty trailing levels from return? Keep all keys for schema stability.
    return levels


def warm_cache_for_curies(
    curies: list[str],
    *,
    refresh: bool = False,
    sleep_s: float = 0.05,
) -> dict[str, Any]:
    cache = load_cache()
    unique = sorted({c.strip() for c in curies if c and str(c).strip()})
    for i, curie in enumerate(unique, 1):
        resolve_path(curie=curie, cache=cache, refresh=refresh, sleep_s=sleep_s)
        if i % 25 == 0 or i == len(unique):
            save_cache(cache)
            print(f"OLS cache: {i}/{len(unique)} curies")
    save_cache(cache)
    return cache


def warm_cache_for_labels(
    labels: list[str],
    *,
    refresh: bool = False,
    sleep_s: float = 0.05,
) -> dict[str, Any]:
    cache = load_cache()
    unique = sorted({str(x).strip() for x in labels if str(x).strip()}, key=str.casefold)
    for i, label in enumerate(unique, 1):
        resolve_path(label=label, cache=cache, refresh=refresh, sleep_s=sleep_s)
        if i % 25 == 0 or i == len(unique):
            save_cache(cache)
            print(f"OLS label cache: {i}/{len(unique)} labels")
    save_cache(cache)
    return cache
