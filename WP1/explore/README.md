# Explore page: species x factor table

**Online: https://fbastian.github.io/BH2026-23-single-cell/**

Static page (React + Vite + MUI, Nivo heatmap, [hyparquet](https://github.com/hyparam/hyparquet)) to browse the merged datasets of the WP1 pipeline. It needs no server: the browser loads two Parquet files and computes the filters, counts and ontology roll-up in memory.

| Piece | Role |
|-------|------|
| [`../scripts/export_explore.py`](../scripts/export_explore.py) | step 6 of the [WP1 pipeline](../README.md): writes `ui/public/datasets.parquet` (one row per dataset) and `ui/public/terms.parquet` (labels and hierarchy of the values) |
| `ui/src/catalogQuery.ts` | loads the Parquet files; filters, facet counts, pivot counts, roll-up |
| `ui/src/components/` | filters (`FacetList`), pivot heatmap (`PivotHeatmap`), dataset cards and table |

## What the page shows

- **Filters** (left): species, tissue, cell type, developmental stage, assay, disease, sex, suspension type, tissue type, resource, flags (merged across resources, several species). Values of a field are combined with OR, fields with AND. Tissue, cell type and stage are trees (composite-metazoan Uberon and CL, `is_a` + `part_of` within the factor domain): the arrow shows the more specific terms, and ticking a term also matches the datasets annotated with any of its descendants. The search box of a tree searches all its terms.
- **Pivot** (default view, opening on species x tissue in roll-up mode): number of datasets for two fields, e.g. species x tissue. For tissue, cell type and stage, each axis is either:
  - **Raw**: the terms as annotated (after remapping); a dataset annotated with "hippocampal formation" counts only in that column;
  - **Roll-up**: a dataset also counts for all the more general terms of its annotations (the hippocampal formation dataset also counts for brain, forebrain, ...). The columns are all the terms under the current term (the root at first), at any depth, sorted by number of datasets ("Show top" keeps the first ones). Click an underlined label to show only the terms under it, use the breadcrumb to go back up, or jump to any term. Datasets annotated with the current term itself and nothing more specific are in the column "... (not more specific)": at the root, these are the datasets without annotation.

  Terms of the subsets tagged in step 5 of the pipeline (Uberon `non_informative`, `upper_level` and `common_anatomy`, and hand-curated terms; e.g. regional part of brain, organ, material anatomical entity) are hidden in the filter trees and the roll-up columns: their more specific terms are shown instead (they still count, through these). In raw mode, terms annotated to datasets are shown even if they are in these subsets.

  The axes follow the side filters of their field: with "brain" ticked in the tissue filter, the tissue roll-up starts under brain (the breadcrumb still goes up); with several tissues ticked, the columns are the terms under each of them, merged (e.g. the parts of brain and of heart); in raw mode, and for the fields without hierarchy (e.g. species), only the selected values (and their more specific terms) are shown, not the other annotations of the matching datasets.

  A dataset counts in every row and column it is annotated with: a dataset with two species counts in both species rows, a dataset with five tissues in five columns. Click a cell to list its datasets (it adds filters, exact ones for raw terms).
- **Cards / Table**: the datasets matching the filters, with links to each resource, the DOI and the H5AD file.

The address bar stays in sync with the current search: layout (`view=cards|table|pivot`), free-text `q`, facet ids (from the terms file), and `page` for cards/table. Copy the URL to bookmark or share a filtered view, e.g. `?view=table&tissue=UBERON:0000955,UBERON:0000948&organism=NCBITaxon:9606`. Pivot is the default layout and is omitted from the query string.

## Run locally

Prerequisite: Node.js 20 or later. From `WP1/`, after steps 1 to 6 of the [pipeline](../README.md):

```bash
cd explore/ui
npm ci
npm run dev        # http://localhost:5173, reloads on code changes
# or the production build:
npm run build && npm run preview
```

After re-running the export, hard-refresh the browser.

## GitHub Pages

[`.github/workflows/deploy-explore-pages.yml`](../../.github/workflows/deploy-explore-pages.yml) builds `ui/` and pushes it to the `gh-pages` branch on every push to `main` that changes `WP1/explore/ui/` (or by hand: Actions, "Deploy explore UI to GitHub Pages", Run workflow). It does not run the Python export: commit the regenerated Parquet files in `ui/public/`.

GitHub Pages is enabled for this repository: the page is at https://fbastian.github.io/BH2026-23-single-cell/. After a push, the new version is online once the workflow and the "pages build and deployment" run have finished (Actions tab, about a minute); hard-refresh the browser.

In a fork, one-time setup: Settings, Pages, Build and deployment, Source "Deploy from a branch", branch `gh-pages`, folder `/ (root)`. The page is then at `https://<owner>.github.io/BH2026-23-single-cell/` (the build uses `VITE_BASE_PATH=/BH2026-23-single-cell/`).
