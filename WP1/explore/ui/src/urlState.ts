import { FACET_FIELDS, type FacetSelection } from "./catalogQuery";
import type { ResultsView } from "./components/ViewToggle";

export type ExploreUrlState = {
  view: ResultsView;
  query: string;
  facets: FacetSelection;
  /** 0-based page for cards/table; ignored in pivot. */
  page: number;
};

const DEFAULT_VIEW: ResultsView = "pivot";

function parseView(raw: string | null): ResultsView {
  return raw === "cards" || raw === "table" || raw === "pivot" ? raw : DEFAULT_VIEW;
}

/** Read filters, layout, search text and page from a query string. */
export function parseExploreUrl(search: string): ExploreUrlState {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const facets: FacetSelection = {};
  for (const field of FACET_FIELDS) {
    const values = (params.get(field) ?? "")
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);
    if (values.length) facets[field] = values;
  }
  const pageRaw = Number.parseInt(params.get("page") ?? "1", 10);
  return {
    view: parseView(params.get("view")),
    query: params.get("q") ?? "",
    facets,
    page: Number.isFinite(pageRaw) && pageRaw > 1 ? pageRaw - 1 : 0,
  };
}

/** Build a query string (no leading `?`) that round-trips with parseExploreUrl. */
export function buildExploreSearch(state: ExploreUrlState): string {
  const params = new URLSearchParams();
  if (state.view !== DEFAULT_VIEW) params.set("view", state.view);
  const q = state.query.trim();
  if (q) params.set("q", q);
  for (const field of FACET_FIELDS) {
    const values = state.facets[field];
    if (!values?.length) continue;
    // Stable order so the same selection always produces the same bookmark.
    params.set(field, [...values].sort().join(","));
  }
  if (state.view !== "pivot" && state.page > 0) {
    params.set("page", String(state.page + 1));
  }
  return params.toString();
}

/** Keep the address bar in sync without adding a history entry (shareable / bookmarkable). */
export function replaceExploreUrl(state: ExploreUrlState): void {
  const search = buildExploreSearch(state);
  const next = `${window.location.pathname}${search ? `?${search}` : ""}${window.location.hash}`;
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (next === current) return;
  window.history.replaceState(window.history.state, "", next);
}
