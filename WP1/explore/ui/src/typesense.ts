import TypesenseInstantSearchAdapter from "typesense-instantsearch-adapter";

export type SearchConfig = {
  host: string;
  port: number;
  protocol: string;
  collection: string;
  api_key: string;
  query_by: string;
  facet_by: string[];
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function loadSearchConfig(): Promise<SearchConfig> {
  const response = await fetch(`${API_BASE}/api/search-config`);
  if (!response.ok) {
    throw new Error(`Failed to load search config (${response.status})`);
  }
  return response.json();
}

/**
 * Prefer same-origin `/typesense` proxy (Vite) so Try Live / remote browsers
 * do not need direct access to Typesense :8108.
 */
function browserTypesenseNode(): {
  host: string;
  port: number;
  protocol: string;
  path: string;
} {
  const { protocol, hostname, port } = window.location;
  const isHttps = protocol === "https:";
  return {
    host: hostname || "localhost",
    port: Number(port || (isHttps ? 443 : 80)),
    protocol: isHttps ? "https" : "http",
    path: "/typesense",
  };
}

export function createSearchClient(config: SearchConfig) {
  const node =
    typeof window !== "undefined"
      ? browserTypesenseNode()
      : {
          host: config.host,
          port: config.port,
          protocol: config.protocol,
          path: "",
        };

  const adapter = new TypesenseInstantSearchAdapter({
    server: {
      apiKey: config.api_key,
      nodes: [node],
      cacheSearchResultsForSeconds: 30,
    },
    additionalSearchParameters: {
      query_by: config.query_by,
      highlight_full_fields: "title,search_blob",
      typo_tokens_threshold: 3,
    },
  });
  return {
    searchClient: adapter.searchClient,
    indexName: config.collection,
    facetBy: config.facet_by,
  };
}
