import type { ExperimentHit } from "./Hit";

export type GroupByField =
  | "none"
  | "source"
  | "organism"
  | "top_organ"
  | "tissue"
  | "assay"
  | "disease"
  | "suspension_type"
  | "study_journal";

export const GROUP_BY_OPTIONS: { value: GroupByField; label: string }[] = [
  { value: "none", label: "None" },
  { value: "source", label: "Source" },
  { value: "organism", label: "Organism" },
  { value: "top_organ", label: "Top organ" },
  { value: "tissue", label: "Tissue" },
  { value: "assay", label: "Assay" },
  { value: "disease", label: "Disease" },
  { value: "suspension_type", label: "Suspension" },
  { value: "study_journal", label: "Journal" },
];

const NONE_LABEL = "(none)";

function valuesForField(hit: ExperimentHit, field: Exclude<GroupByField, "none">): string[] {
  const raw = hit[field];
  if (Array.isArray(raw)) {
    const cleaned = [...new Set(raw.map((v) => String(v).trim()).filter(Boolean))];
    return cleaned.length ? cleaned : [NONE_LABEL];
  }
  if (typeof raw === "string" && raw.trim() && raw !== "unknown") {
    return [raw.trim()];
  }
  return [NONE_LABEL];
}

export type HitGroup = {
  key: string;
  label: string;
  hits: ExperimentHit[];
};

/** Group current page hits under section keys. Multi-valued fields explode into each value. */
export function groupHits(hits: ExperimentHit[], field: GroupByField): HitGroup[] {
  if (field === "none") {
    return [{ key: "__all__", label: "All results", hits }];
  }

  const buckets = new Map<string, ExperimentHit[]>();
  for (const hit of hits) {
    for (const value of valuesForField(hit, field)) {
      const list = buckets.get(value);
      if (list) {
        if (!list.some((existing) => existing.objectID === hit.objectID)) {
          list.push(hit);
        }
      } else {
        buckets.set(value, [hit]);
      }
    }
  }

  return [...buckets.entries()]
    .map(([key, grouped]) => ({ key, label: key, hits: grouped }))
    .sort((a, b) => {
      if (a.key === NONE_LABEL) return 1;
      if (b.key === NONE_LABEL) return -1;
      return a.label.localeCompare(b.label, undefined, { sensitivity: "base" });
    });
}
