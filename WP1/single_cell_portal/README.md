# Single Cell Portal study catalog (WP1)

Snapshot of study metadata from the Broad Institute [Single Cell Portal](https://singlecell.broadinstitute.org/) search API, for unified discovery with Fenix in `WP1/explore/`.

## Contents

| File | Purpose |
|------|---------|
| [`download_studies.py`](download_studies.py) | Paginated download + schema/facet summary |
| [`download_studies.sh`](download_studies.sh) | Thin shell wrapper |
| [`studies.json`](studies.json) | Full cached payload (`studies`, totals, accessions) |
| [`studies.sample.json`](studies.sample.json) | First 2 studies |
| [`studies.schema-summary.json`](studies.schema-summary.json) | Field list + facet cardinalities |

## Refresh

```bash
python3 WP1/single_cell_portal/download_studies.py --summarize
# or
WP1/single_cell_portal/download_studies.sh
```

Source URL (default):

`https://singlecell.broadinstitute.org/single_cell/api/v1/search?type=study`

The API returns ~10 studies per page; the script walks `total_pages`.

## Mapping into the explore index

The Typesense indexer (`WP1/explore/indexer/`) flattens each study with `source=single_cell_portal` and maps:

| Typesense field | SCP field |
|-----------------|-----------|
| `organism` | `metadata.species` |
| `tissue` / `top_organ` | `metadata.organ` |
| `assay` | `metadata.library_preparation_protocol` |
| `disease` | `metadata.disease` |
| `sex` | `metadata.sex` |
| `cell_type` | *not present in this search API payload* |
| `development_stage` | *not present in this search API payload* |
| `cell_count` / `feature_count` | `cell_count` / `gene_count` |
| `explorer_url` | `https://singlecell.broadinstitute.org` + `study_url` |

SCP study search metadata currently exposes only `species`, `organ`, `disease`, `sex`, and `library_preparation_protocol` (plus ~half of studies have empty metadata). Cell type / developmental stage facets therefore come from Fenix only until SCP provides them.
