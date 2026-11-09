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

export function createSearchClient(config: SearchConfig) {
  const adapter = new TypesenseInstantSearchAdapter({
    server: {
      apiKey: config.api_key,
      nodes: [
        {
          host: config.host,
          port: config.port,
          protocol: config.protocol,
        },
      ],
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
