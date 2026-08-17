// The filter vocabulary, client side — story 020.
//
// The backend's `FilterSet` is the definition; this is its mirror, and the two agree on one thing
// that matters more than the rest: **the URL is the state**. Filters live in the query string, not
// in a `useState` that a reload discards, because that is what makes a filtered collection a
// shareable artifact and what makes the back button behave.
//
// Story 020's technical note is blunt about the cost of getting this wrong: *"retrofitting it later
// means rewriting every filter component."* So it is here, in one file, before any component
// exists.
//
// The same shape goes into `saved_views.filters`. One encoding, so a saved view and a shared link
// cannot come to mean different things.

/** Attributes that take several values and OR within themselves. Order is the filter rail's. */
export const MULTI_VALUE = [
  "set_code", "element", "rarity", "condition", "finish", "language",
] as const;

/** Tri-state. `undefined` is a real third state: "not filtering" ≠ "filtering for false". */
export const TRISTATE = ["is_graded", "is_for_trade"] as const;

export type MultiKey = (typeof MULTI_VALUE)[number];
export type TriKey = (typeof TRISTATE)[number];

export type Filters = Partial<Record<MultiKey, string[]>> &
  Partial<Record<TriKey, boolean>> & { q?: string };

export type Sort =
  | "added_desc" | "added_asc" | "quantity_desc" | "quantity_asc" | "name_asc" | "name_desc";

export type Density = "comfortable" | "compact";

export const SORT_LABELS: Record<Sort, string> = {
  added_desc: "Newest first",
  added_asc: "Oldest first",
  quantity_desc: "Most copies",
  quantity_asc: "Fewest copies",
  name_asc: "Name A–Z",
  name_desc: "Name Z–A",
};

/** Fixed per density mode. Variable row heights are the usual cause of stutter in a virtualized
 *  table, and much harder to remove later than to avoid now — story 019 says so explicitly. */
export const ROW_HEIGHT: Record<Density, number> = { comfortable: 56, compact: 36 };

export function parseFilters(params: URLSearchParams): Filters {
  const filters: Filters = {};

  for (const key of MULTI_VALUE) {
    const values = params.getAll(key).filter(Boolean);
    if (values.length) filters[key] = values;
  }
  for (const key of TRISTATE) {
    const raw = params.get(key);
    if (raw === "true") filters[key] = true;
    else if (raw === "false") filters[key] = false;
  }
  const q = params.get("q");
  if (q) filters.q = q;

  return filters;
}

export function toSearchParams(
  filters: Filters,
  extra: { sort?: Sort; cursor?: string } = {},
): URLSearchParams {
  const params = new URLSearchParams();

  for (const key of MULTI_VALUE) {
    for (const value of filters[key] ?? []) params.append(key, value);
  }
  for (const key of TRISTATE) {
    const value = filters[key];
    // `!== undefined`, not truthiness. `is_graded=false` means "ungraded only" and dropping it
    // because it is falsy silently turns that view into "everything".
    if (value !== undefined) params.set(key, String(value));
  }
  if (filters.q) params.set("q", filters.q);

  if (extra.sort && extra.sort !== "added_desc") params.set("sort", extra.sort);
  if (extra.cursor) params.set("cursor", extra.cursor);

  return params;
}

/** How many attributes are narrowing the view. Drives the "clear all" affordance and the badge. */
export function activeFilterCount(filters: Filters): number {
  let count = 0;
  for (const key of MULTI_VALUE) count += (filters[key]?.length ?? 0) > 0 ? 1 : 0;
  for (const key of TRISTATE) count += filters[key] !== undefined ? 1 : 0;
  if (filters.q) count += 1;
  return count;
}

/** A sentence naming what is currently filtered — for the empty state.
 *
 *  "No cards match Fire, Near Mint" tells a collector what to loosen. "No results" does not, and
 *  is indistinguishable from the collection being empty, which is a completely different fact. */
export function describeFilters(filters: Filters): string {
  const parts: string[] = [];
  for (const key of MULTI_VALUE) {
    const values = filters[key];
    if (values?.length) parts.push(values.map(humanise).join(" or "));
  }
  if (filters.is_graded !== undefined) parts.push(filters.is_graded ? "graded" : "ungraded");
  if (filters.is_for_trade !== undefined) {
    parts.push(filters.is_for_trade ? "for trade" : "not for trade");
  }
  if (filters.q) parts.push(`“${filters.q}”`);
  return parts.join(", ");
}

export function humanise(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Add or remove one value from a multi-value attribute, immutably. */
export function toggleValue(filters: Filters, key: MultiKey, value: string): Filters {
  const current = filters[key] ?? [];
  const next = current.includes(value)
    ? current.filter((v) => v !== value)
    : [...current, value];
  const out = { ...filters };
  if (next.length) out[key] = next;
  else delete out[key];
  return out;
}

/** Cycle a tri-state: unset → true → false → unset. The third click clears it, which is how a
 *  user gets back to "either" without hunting for a reset. */
export function cycleTristate(filters: Filters, key: TriKey): Filters {
  const out = { ...filters };
  if (filters[key] === undefined) out[key] = true;
  else if (filters[key] === true) out[key] = false;
  else delete out[key];
  return out;
}
