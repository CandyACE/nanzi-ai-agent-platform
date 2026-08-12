/** Canonical join_type values persisted by the relationship editor. */
export type RelationshipJoinType = "left" | "inner" | "one_to_one";

const JOIN_TYPE_LABELS: Record<RelationshipJoinType, string> = {
  left: "Left · 一对多 (1:N)",
  inner: "Inner Join",
  one_to_one: "One to One",
};

/**
 * Normalize legacy / AI-imported aliases onto the three editor values.
 * `ONE_TO_MANY` / `many_to_one` map to Left Join (1:N).
 */
export function normalizeRelationshipJoinType(
  raw: string | null | undefined,
): RelationshipJoinType {
  const key = String(raw || "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");

  if (key === "inner" || key === "inner_join") {
    return "inner";
  }
  if (
    key === "one_to_one" ||
    key === "onetoone" ||
    key === "1_1" ||
    key === "1:1"
  ) {
    return "one_to_one";
  }
  // left / LEFT / one_to_many / ONE_TO_MANY / many_to_one / unknown → left
  return "left";
}

/** Human-readable badge label for list / graph display. */
export function formatRelationshipJoinTypeLabel(
  raw: string | null | undefined,
): string {
  return JOIN_TYPE_LABELS[normalizeRelationshipJoinType(raw)];
}
