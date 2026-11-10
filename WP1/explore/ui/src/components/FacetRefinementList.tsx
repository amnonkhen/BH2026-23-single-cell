import { useRef, useState } from "react";
import { useRefinementList } from "react-instantsearch";

type Props = {
  attribute: string;
  searchable?: boolean;
  searchablePlaceholder?: string;
  showMore?: boolean;
  limit?: number;
  showMoreLimit?: number;
};

/**
 * Like InstantSearch RefinementList, but keeps the facet search query after
 * selecting a value so users can multi-select from the same filtered list.
 */
export function FacetRefinementList({
  attribute,
  searchable = false,
  searchablePlaceholder = "Search…",
  showMore = false,
  limit = 8,
  showMoreLimit = 50,
}: Props) {
  const {
    items,
    refine,
    searchForItems,
    canToggleShowMore,
    isShowingMore,
    toggleShowMore,
    isFromSearch,
  } = useRefinementList({
    attribute,
    limit,
    showMore,
    showMoreLimit,
  });

  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const setQueryAndSearch = (next: string) => {
    setQuery(next);
    searchForItems(next);
  };

  return (
    <div className="ais-RefinementList">
      {searchable ? (
        <div className="ais-RefinementList-searchBox">
          <form
            className="ais-SearchBox-form"
            noValidate
            onSubmit={(event) => {
              // Keep query; Enter should not clear or auto-pick the first hit.
              event.preventDefault();
            }}
          >
            <input
              ref={inputRef}
              className="ais-SearchBox-input"
              type="search"
              placeholder={searchablePlaceholder}
              value={query}
              onChange={(event) => setQueryAndSearch(event.currentTarget.value)}
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
            />
            {query ? (
              <button
                type="button"
                className="ais-SearchBox-reset"
                title="Clear facet search"
                onClick={() => {
                  setQueryAndSearch("");
                  inputRef.current?.focus();
                }}
              >
                ✕
              </button>
            ) : null}
          </form>
        </div>
      ) : null}

      {searchable && isFromSearch && items.length === 0 ? (
        <p className="facet-no-results">No matching values</p>
      ) : (
        <ul className="ais-RefinementList-list">
          {items.map((item) => (
            <li
              key={item.value}
              className={
                item.isRefined
                  ? "ais-RefinementList-item ais-RefinementList-item--selected"
                  : "ais-RefinementList-item"
              }
            >
              <label className="ais-RefinementList-label">
                <input
                  className="ais-RefinementList-checkbox"
                  type="checkbox"
                  checked={item.isRefined}
                  onChange={() => {
                    // Refine without clearing the facet search query.
                    refine(item.value);
                  }}
                />
                <span className="ais-RefinementList-labelText">{item.label}</span>
                <span className="ais-RefinementList-count">{item.count}</span>
              </label>
            </li>
          ))}
        </ul>
      )}

      {showMore && canToggleShowMore ? (
        <button
          type="button"
          className="ais-RefinementList-showMore"
          onClick={toggleShowMore}
        >
          {isShowingMore ? "Show less" : "Show more"}
        </button>
      ) : null}
    </div>
  );
}
