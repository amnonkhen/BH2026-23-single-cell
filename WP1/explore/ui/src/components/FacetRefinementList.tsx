import { useRefinementList } from "react-instantsearch";

type Props = {
  attribute: string;
  searchable?: boolean;
  limit?: number;
  showMoreLimit?: number;
  searchablePlaceholder?: string;
};

/**
 * Stock-like RefinementList that hides Show more when all values already fit
 * in `limit` (InstantSearch sets canToggleShowMore=false in that case).
 */
export function FacetRefinementList({
  attribute,
  searchable = false,
  limit = 8,
  showMoreLimit = 30,
  searchablePlaceholder,
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
    showMore: true,
    showMoreLimit,
  });

  return (
    <div
      className={[
        "ais-RefinementList",
        items.length === 0 ? "ais-RefinementList--noRefinement" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {searchable ? (
        <div className="ais-RefinementList-searchBox">
          <input
            className="ais-SearchBox-input"
            type="search"
            placeholder={searchablePlaceholder}
            onChange={(event) => searchForItems(event.currentTarget.value)}
          />
        </div>
      ) : null}
      {items.length === 0 && isFromSearch ? (
        <div className="ais-RefinementList-noResults">No matching values</div>
      ) : (
        <ul className="ais-RefinementList-list">
          {items.map((item) => (
            <li
              key={item.value}
              className={[
                "ais-RefinementList-item",
                item.isRefined ? "ais-RefinementList-item--selected" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <label className="ais-RefinementList-label">
                <input
                  className="ais-RefinementList-checkbox"
                  type="checkbox"
                  checked={item.isRefined}
                  value={item.value}
                  onChange={() => refine(item.value)}
                />
                <span className="ais-RefinementList-labelText">{item.label}</span>
                <span className="ais-RefinementList-count">{item.count}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      {canToggleShowMore ? (
        <button
          type="button"
          className="ais-RefinementList-showMore"
          onClick={toggleShowMore}
          aria-expanded={isShowingMore}
        >
          {isShowingMore ? "Show less" : "Show more"}
        </button>
      ) : null}
    </div>
  );
}
