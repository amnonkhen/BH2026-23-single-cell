import { useHierarchicalMenu } from "react-instantsearch";

const TISSUE_HIERARCHY_ATTRIBUTES = [
  "tissue_hierarchy.lvl0",
  "tissue_hierarchy.lvl1",
  "tissue_hierarchy.lvl2",
  "tissue_hierarchy.lvl3",
  "tissue_hierarchy.lvl4",
  "tissue_hierarchy.lvl5",
];

type Item = {
  label: string;
  value: string;
  count: number;
  isRefined: boolean;
  data: Item[] | null;
};

function HierarchyList({
  items,
  refine,
  createURL,
}: {
  items: Item[];
  refine: (value: string) => void;
  createURL: (value: string) => string;
}) {
  if (!items.length) return null;
  return (
    <ul className="ais-HierarchicalMenu-list">
      {items.map((item) => (
        <li
          key={item.value}
          className={[
            "ais-HierarchicalMenu-item",
            item.isRefined ? "ais-HierarchicalMenu-item--selected" : "",
            item.data && item.data.length
              ? "ais-HierarchicalMenu-item--parent"
              : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <a
            className={[
              "ais-HierarchicalMenu-link",
              item.isRefined ? "ais-HierarchicalMenu-link--selected" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            href={createURL(item.value)}
            onClick={(event) => {
              event.preventDefault();
              refine(item.value);
            }}
          >
            <span className="ais-HierarchicalMenu-label">{item.label}</span>
            <span className="ais-HierarchicalMenu-count">{item.count}</span>
          </a>
          {item.data && item.data.length > 0 ? (
            <ul className="ais-HierarchicalMenu-list ais-HierarchicalMenu-list--child">
              {item.data.map((child) => (
                <li
                  key={child.value}
                  className={[
                    "ais-HierarchicalMenu-item",
                    child.isRefined ? "ais-HierarchicalMenu-item--selected" : "",
                    child.data && child.data.length
                      ? "ais-HierarchicalMenu-item--parent"
                      : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <a
                    className={[
                      "ais-HierarchicalMenu-link",
                      child.isRefined
                        ? "ais-HierarchicalMenu-link--selected"
                        : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    href={createURL(child.value)}
                    onClick={(event) => {
                      event.preventDefault();
                      refine(child.value);
                    }}
                  >
                    <span className="ais-HierarchicalMenu-label">
                      {child.label}
                    </span>
                    <span className="ais-HierarchicalMenu-count">
                      {child.count}
                    </span>
                  </a>
                  {child.data && child.data.length > 0 ? (
                    <HierarchyList
                      items={child.data}
                      refine={refine}
                      createURL={createURL}
                    />
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

/**
 * InstantSearch HierarchicalMenu wired for Typesense `tissue_hierarchy.lvlN`.
 * Renders Show more only when InstantSearch says more values exist.
 */
export function TissueHierarchyMenu() {
  const {
    items,
    refine,
    createURL,
    canToggleShowMore,
    isShowingMore,
    toggleShowMore,
    canRefine,
  } = useHierarchicalMenu({
    attributes: TISSUE_HIERARCHY_ATTRIBUTES,
    separator: " > ",
    limit: 12,
    showMore: true,
    showMoreLimit: 40,
    sortBy: ["count:desc"],
  });

  if (!canRefine && items.length === 0) {
    return (
      <p className="facet-empty">
        No tissue hierarchy values in this result set.
      </p>
    );
  }

  return (
    <div
      className={[
        "ais-HierarchicalMenu",
        items.length === 0 ? "ais-HierarchicalMenu--noRefinement" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <HierarchyList items={items as Item[]} refine={refine} createURL={createURL} />
      {canToggleShowMore ? (
        <button
          type="button"
          className="ais-HierarchicalMenu-showMore"
          onClick={toggleShowMore}
          aria-expanded={isShowingMore}
        >
          {isShowingMore ? "Show less" : "Show more"}
        </button>
      ) : null}
    </div>
  );
}
