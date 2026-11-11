/**
 * In-browser catalog engine.
 *
 * Loads experiments.parquet with hyparquet (pure JS, ~300KB) and runs
 * filter / facet / pivot in memory. DuckDB-WASM was dropped because its
 * ~34MB .wasm payload dominated cold start (~30s).
 */
import { parquetReadObjects } from "hyparquet";
import { compressors } from "hyparquet-compressors";

/** Cache-bust so GitHub Pages / browsers cannot keep a stale HTML 404 as parquet. */
export const PARQUET_URL = `${import.meta.env.BASE_URL}experiments.parquet?v=4`;

export type FacetSelection = Record<string, string[]>;

export const LIST_FACETS = [
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
] as const;

export const STRING_FACETS = ["source", "study_journal"] as const;

export type ListFacet = (typeof LIST_FACETS)[number];
export type StringFacet = (typeof STRING_FACETS)[number];
export type FacetField = ListFacet | StringFacet;

export type ExperimentRow = {
  objectID: string;
  id: string;
  title?: string;
  source?: string;
  organism?: string[];
  top_organ?: string[];
  tissue?: string[];
  assay?: string[];
  disease?: string[];
  cell_type?: string[];
  development_stage?: string[];
  suspension_type?: string[];
  cell_count?: number;
  feature_count?: number;
  explorer_url?: string;
  experiment_id?: string;
  study_journal?: string;
  search_blob?: string;
  [key: string]: unknown;
};

export type FacetCount = { value: string; count: number };

export type PivotResult = {
  rows: string[];
  cols: string[];
  matrix: number[][];
  maxCell: number;
  found: number;
};

let catalogPromise: Promise<ExperimentRow[]> | null = null;

function asStringArray(value: unknown): string[] | undefined {
  if (value == null) return undefined;
  if (Array.isArray(value)) return value.map(String).filter((v) => v.length > 0);
  return [String(value)];
}

function mapRow(row: Record<string, unknown>): ExperimentRow {
  const id = String(row.id ?? "");
  return {
    ...row,
    objectID: id,
    id,
    title: row.title != null ? String(row.title) : undefined,
    source: row.source != null ? String(row.source) : undefined,
    organism: asStringArray(row.organism),
    top_organ: asStringArray(row.top_organ),
    tissue: asStringArray(row.tissue),
    tissue_type: asStringArray(row.tissue_type),
    assay: asStringArray(row.assay),
    disease: asStringArray(row.disease),
    cell_type: asStringArray(row.cell_type),
    development_stage: asStringArray(row.development_stage),
    suspension_type: asStringArray(row.suspension_type),
    sex: asStringArray(row.sex),
    self_reported_ethnicity: asStringArray(row.self_reported_ethnicity),
    cell_count: row.cell_count != null ? Number(row.cell_count) : 0,
    feature_count: row.feature_count != null ? Number(row.feature_count) : undefined,
    explorer_url: row.explorer_url != null ? String(row.explorer_url) : undefined,
    experiment_id:
      row.experiment_id != null ? String(row.experiment_id) : undefined,
    study_journal:
      row.study_journal != null ? String(row.study_journal) : undefined,
    search_blob: row.search_blob != null ? String(row.search_blob) : undefined,
  };
}

function assertParquetMagic(buffer: ArrayBuffer, url: string): void {
  if (buffer.byteLength < 8) {
    throw new Error(
      `Parquet too short (${buffer.byteLength} bytes) from ${url}. Hard-refresh or re-export: python indexer/export_parquet.py`
    );
  }
  const bytes = new Uint8Array(buffer);
  const head = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]);
  const tail = String.fromCharCode(
    bytes[bytes.length - 4],
    bytes[bytes.length - 3],
    bytes[bytes.length - 2],
    bytes[bytes.length - 1]
  );
  if (head !== "PAR1" || tail !== "PAR1") {
    const sniff = new TextDecoder().decode(bytes.slice(0, 64)).replace(/\s+/g, " ").slice(0, 48);
    throw new Error(
      `Invalid parquet from ${url} (got head=${JSON.stringify(head)} tail=${JSON.stringify(tail)}; starts ${JSON.stringify(sniff)}). Hard-refresh the page, or re-export: python indexer/export_parquet.py`
    );
  }
}

async function loadCatalog(): Promise<ExperimentRow[]> {
  if (!catalogPromise) {
    catalogPromise = (async () => {
      // Full-file fetch (not range/URL mode): GitHub Pages gzips .parquet and
      // applies byte ranges to the gzip stream, which breaks hyparquet footers.
      // no-store avoids 304 reuse of a previously cached HTML/error body.
      const response = await fetch(PARQUET_URL, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(
          `Failed to fetch ${PARQUET_URL} (${response.status}). Run: python indexer/export_parquet.py`
        );
      }
      const buffer = await response.arrayBuffer();
      assertParquetMagic(buffer, PARQUET_URL);
      const rows = await parquetReadObjects({
        file: buffer,
        compressors,
      });
      return (rows as Record<string, unknown>[]).map(mapRow);
    })().catch((err) => {
      catalogPromise = null;
      throw err;
    });
  }
  return catalogPromise;
}

/** Kept for App.tsx boot path compatibility. */
export async function getConnection(): Promise<void> {
  await loadCatalog();
}

export function isListFacet(field: string): field is ListFacet {
  return (LIST_FACETS as readonly string[]).includes(field);
}

function fieldValues(row: ExperimentRow, field: string): string[] {
  const raw = row[field];
  if (Array.isArray(raw)) {
    return raw.map(String).filter(Boolean);
  }
  if (raw == null) return [];
  const text = String(raw).trim();
  return text ? [text] : [];
}

function rowMatchesFacets(
  row: ExperimentRow,
  facets: FacetSelection,
  omitFacet?: string
): boolean {
  for (const [field, values] of Object.entries(facets)) {
    if (!values.length || field === omitFacet) continue;
    const present = new Set(fieldValues(row, field));
    const hit = values.some((wanted) => present.has(wanted));
    if (!hit) return false;
  }
  return true;
}

function rowMatchesQuery(row: ExperimentRow, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystacks = [row.title, row.search_blob, row.experiment_id, row.id]
    .filter(Boolean)
    .map((v) => String(v).toLowerCase());
  return haystacks.some((text) => text.includes(q));
}

function filteredRows(
  rows: ExperimentRow[],
  query: string,
  facets: FacetSelection,
  omitFacet?: string
): ExperimentRow[] {
  return rows.filter(
    (row) => rowMatchesQuery(row, query) && rowMatchesFacets(row, facets, omitFacet)
  );
}

export async function facetCounts(
  field: FacetField,
  query: string,
  facets: FacetSelection,
  limit = 40
): Promise<FacetCount[]> {
  const rows = filteredRows(await loadCatalog(), query, facets, field);
  const counts = new Map<string, number>();
  for (const row of rows) {
    const values = [...new Set(fieldValues(row, field))];
    for (const value of values) {
      if (!value) continue;
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
    .slice(0, limit);
}

export async function searchRows(
  query: string,
  facets: FacetSelection,
  options: { offset: number; limit: number }
): Promise<{ rows: ExperimentRow[]; found: number }> {
  const { offset, limit } = options;
  const matched = filteredRows(await loadCatalog(), query, facets).sort((a, b) => {
    const byCells = (b.cell_count ?? 0) - (a.cell_count ?? 0);
    if (byCells !== 0) return byCells;
    return String(a.title ?? "").localeCompare(String(b.title ?? ""));
  });
  return {
    found: matched.length,
    rows: matched.slice(offset, offset + limit),
  };
}

export async function pivotCounts(
  rowField: FacetField,
  colField: FacetField,
  query: string,
  facets: FacetSelection,
  options: { maxRows?: number; maxCols?: number } = {}
): Promise<PivotResult> {
  const maxRows = options.maxRows ?? 18;
  const maxCols = options.maxCols ?? 14;
  const matched = filteredRows(await loadCatalog(), query, facets);
  const pairCounts = new Map<string, number>();
  const rowTotals = new Map<string, number>();
  const colTotals = new Map<string, number>();

  for (const row of matched) {
    const rowVals = fieldValues(row, rowField);
    const colVals = fieldValues(row, colField);
    const rows = rowVals.length ? rowVals : ["(none)"];
    const cols = colVals.length ? colVals : ["(none)"];
    // Count distinct id once per (row,col) pair
    const seen = new Set<string>();
    for (const r of rows) {
      for (const c of cols) {
        const key = `${r}\0${c}`;
        if (seen.has(key)) continue;
        seen.add(key);
        pairCounts.set(key, (pairCounts.get(key) ?? 0) + 1);
        rowTotals.set(r, (rowTotals.get(r) ?? 0) + 1);
        colTotals.set(c, (colTotals.get(c) ?? 0) + 1);
      }
    }
  }

  const rowOrder = [...rowTotals.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, maxRows)
    .map(([value]) => value);
  const colOrder = [...colTotals.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, maxCols)
    .map(([value]) => value);

  let maxCell = 0;
  const matrix = rowOrder.map((r) =>
    colOrder.map((c) => {
      const n = pairCounts.get(`${r}\0${c}`) ?? 0;
      if (n > maxCell) maxCell = n;
      return n;
    })
  );

  return {
    rows: rowOrder,
    cols: colOrder,
    matrix,
    maxCell,
    found: matched.length,
  };
}
