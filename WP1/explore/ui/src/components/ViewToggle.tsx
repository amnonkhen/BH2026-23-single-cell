import type { ReactNode } from "react";

export type ResultsView = "cards" | "table";

const OPTIONS: { id: ResultsView; label: string; icon: ReactNode }[] = [
  {
    id: "cards",
    label: "Cards",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
        <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.2" fill="currentColor" />
        <rect x="9" y="1.5" width="5.5" height="5.5" rx="1.2" fill="currentColor" />
        <rect x="1.5" y="9" width="5.5" height="5.5" rx="1.2" fill="currentColor" />
        <rect x="9" y="9" width="5.5" height="5.5" rx="1.2" fill="currentColor" />
      </svg>
    ),
  },
  {
    id: "table",
    label: "Table",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
        <rect x="1.5" y="2" width="13" height="2.2" rx="0.6" fill="currentColor" />
        <rect x="1.5" y="6.9" width="13" height="2.2" rx="0.6" fill="currentColor" />
        <rect x="1.5" y="11.8" width="13" height="2.2" rx="0.6" fill="currentColor" />
      </svg>
    ),
  },
];

type Props = {
  value: ResultsView;
  onChange: (view: ResultsView) => void;
};

export function ViewToggle({ value, onChange }: Props) {
  return (
    <div className="view-toggle" role="group" aria-label="Results layout">
      {OPTIONS.map((option) => {
        const selected = value === option.id;
        return (
          <button
            key={option.id}
            type="button"
            className={selected ? "view-toggle-btn is-active" : "view-toggle-btn"}
            aria-pressed={selected}
            onClick={() => onChange(option.id)}
          >
            {option.icon}
            <span>{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
