type RefinementLike = {
  attribute: string;
  refinements: Array<{ value?: string | number | boolean }>;
};

/** Escape a value for Typesense backtick-quoted filter literals. */
function escapeFilterValue(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/`/g, "\\`");
}

/**
 * Convert InstantSearch current refinements into a Typesense `filter_by` string.
 * Same-attribute values are OR'd; different attributes are AND'd.
 */
export function refinementsToFilterBy(items: RefinementLike[]): string | null {
  const parts: string[] = [];

  for (const item of items) {
    const values = item.refinements
      .map((refinement) => String(refinement.value ?? "").trim())
      .filter(Boolean);
    if (!values.length) continue;

    if (values.length === 1) {
      parts.push(`${item.attribute}:=\`${escapeFilterValue(values[0])}\``);
      continue;
    }

    const joined = values
      .map((value) => `\`${escapeFilterValue(value)}\``)
      .join(",");
    parts.push(`${item.attribute}:=[${joined}]`);
  }

  return parts.length ? parts.join(" && ") : null;
}
