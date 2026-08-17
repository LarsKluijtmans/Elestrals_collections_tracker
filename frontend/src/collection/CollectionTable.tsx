import { Box, Checkbox, Stack, Typography } from "@mui/material";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";
import { Link } from "react-router-dom";
import type { CollectionRow } from "../api/backend";
import { ElementChip } from "../components/ElementChip";
import { RarityBadge } from "../components/RarityBadge";
import { QuantityStepper } from "./QuantityStepper";
import { ROW_HEIGHT, type Density, type Sort } from "./filters";

/**
 * The collection table — story 019.
 *
 * **Row height is fixed per density mode and known before render.** Variable-height virtualization
 * is the usual cause of stutter in tables like this, and the story is explicit that it is far
 * harder to remove later than to avoid now. `ROW_HEIGHT` is the single source of that number, and
 * the image box reserves its aspect ratio so nothing reflows when art arrives.
 *
 * Encoding rules from the design system, and each is load-bearing rather than decorative:
 *
 * * **Element owns hue** — a named tinted chip, never colour alone.
 * * **Rarity is a material**, never a hue. Two hue encodings in one row is unreadable.
 * * **Condition is a neutral badge with a letter grade.** No colour at all.
 */

const COLUMNS = [
  { key: "select", width: 44, label: "" },
  { key: "art", width: 44, label: "" },
  { key: "name", width: 0, label: "Card" },
  { key: "set", width: 110, label: "Set" },
  { key: "element", width: 110, label: "Element" },
  { key: "rarity", width: 120, label: "Rarity" },
  { key: "condition", width: 90, label: "Condition" },
  { key: "quantity", width: 140, label: "Quantity" },
  { key: "added", width: 110, label: "Added" },
] as const;

const SORTABLE: Partial<Record<(typeof COLUMNS)[number]["key"], [Sort, Sort]>> = {
  name: ["name_asc", "name_desc"],
  quantity: ["quantity_desc", "quantity_asc"],
  added: ["added_desc", "added_asc"],
};

export function CollectionTable({
  rows, density, sort, selected, allSelected, loading,
  onSort, onToggle, onToggleAll, onQuantity, onReachEnd,
}: {
  rows: CollectionRow[];
  density: Density;
  sort: Sort;
  selected: Set<string>;
  allSelected: boolean;
  loading: boolean;
  onSort: (sort: Sort) => void;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  onQuantity: (row: CollectionRow, quantity: number) => void;
  onReachEnd: () => void;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const rowHeight = ROW_HEIGHT[density];

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    // Constant, not measured. This is what keeps scrolling smooth at 10,000 rows.
    estimateSize: () => rowHeight,
    overscan: 8,
  });

  const items = virtualizer.getVirtualItems();
  const last = items[items.length - 1];
  // Fetch the next page while there is still a screenful left, so the scroll never stops at the
  // bottom waiting for a request that could have started earlier.
  if (last && last.index >= rows.length - 10 && !loading) onReachEnd();

  return (
    <Stack sx={{ flex: 1, minWidth: 0 }}>
      <Stack
        direction="row"
        role="row"
        sx={{
          gap: 1, px: 1, py: 1, borderBottom: 1, borderColor: "divider",
          position: "sticky", top: 0, bgcolor: "background.paper", zIndex: 1,
        }}
      >
        {COLUMNS.map((column) => {
          const sortable = SORTABLE[column.key];
          const isActive = sortable?.includes(sort);
          return (
            <Box
              key={column.key}
              role="columnheader"
              aria-sort={
                isActive ? (sort.endsWith("_asc") ? "ascending" : "descending") : undefined
              }
              sx={{
                width: column.width || undefined,
                flex: column.width ? "0 0 auto" : 1,
                minWidth: 0,
              }}
            >
              {column.key === "select" ? (
                <Checkbox
                  size="small"
                  checked={allSelected}
                  indeterminate={!allSelected && selected.size > 0}
                  onChange={onToggleAll}
                  slotProps={{ input: { "aria-label": "Select all rows" } }}
                />
              ) : sortable ? (
                <Box
                  component="button"
                  type="button"
                  onClick={() => onSort(sort === sortable[0] ? sortable[1] : sortable[0])}
                  sx={{
                    all: "unset", cursor: "pointer", fontSize: 12, fontWeight: 600,
                    color: isActive ? "text.primary" : "text.secondary",
                    "&:focus-visible": { outline: "2px solid", outlineOffset: 2 },
                  }}
                >
                  {column.label}
                  {isActive ? (sort.endsWith("_asc") ? " ▲" : " ▼") : ""}
                </Box>
              ) : (
                <Typography sx={{ fontSize: 12, color: "text.secondary", fontWeight: 600 }}>
                  {column.label}
                </Typography>
              )}
            </Box>
          );
        })}
      </Stack>

      <Box
        ref={parentRef}
        role="rowgroup"
        sx={{ overflowY: "auto", maxHeight: "calc(100vh - 260px)", contain: "strict" }}
      >
        <Box sx={{ height: virtualizer.getTotalSize(), position: "relative" }}>
          {items.map((virtualRow) => {
            const row = rows[virtualRow.index];
            return (
              <Stack
                key={row.id}
                direction="row"
                role="row"
                sx={{
                  gap: 1, px: 1, alignItems: "center",
                  position: "absolute", top: 0, left: 0, right: 0,
                  height: rowHeight,
                  transform: `translateY(${virtualRow.start}px)`,
                  borderBottom: 1, borderColor: "divider",
                  bgcolor: selected.has(row.id) ? "action.selected" : undefined,
                }}
              >
                <Box sx={{ width: 44, flex: "0 0 auto" }}>
                  <Checkbox
                    size="small"
                    checked={selected.has(row.id)}
                    onChange={() => onToggle(row.id)}
                    slotProps={{ input: { "aria-label": `Select ${row.name}` } }}
                  />
                </Box>

                <Box
                  sx={{
                    width: 44, flex: "0 0 auto",
                    // Reserved before the image exists. The grid must not reflow under a
                    // clicking finger, and a skeleton of the wrong size is a reflow.
                    aspectRatio: "5 / 7", height: rowHeight - 8,
                    bgcolor: "action.hover", borderRadius: 0.5, overflow: "hidden",
                  }}
                >
                  {row.image_url ? (
                    <Box
                      component="img"
                      src={row.image_url}
                      alt={row.alt_text}
                      loading="lazy"
                      sx={{ width: "100%", height: "100%", objectFit: "cover" }}
                      // A 404 image must never become a broken-image icon. The placeholder box
                      // underneath already reserves the space, so hiding the img is enough.
                      onError={(event) => {
                        (event.currentTarget as HTMLImageElement).style.display = "none";
                      }}
                    />
                  ) : null}
                </Box>

                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography
                    component={Link}
                    to={`/cards/${row.card_id}`}
                    title={row.name}
                    noWrap
                    sx={{ fontSize: 14, display: "block", color: "inherit" }}
                  >
                    {row.name}
                  </Typography>
                </Box>

                <Typography sx={{ width: 110, flex: "0 0 auto", fontSize: 12 }} noWrap>
                  {row.set_code} {row.collector_number}
                </Typography>

                <Box sx={{ width: 110, flex: "0 0 auto" }}>
                  {row.element ? <ElementChip element={row.element} /> : null}
                </Box>

                <Box sx={{ width: 120, flex: "0 0 auto" }}>
                  <RarityBadge rarity={row.rarity} />
                </Box>

                <Box sx={{ width: 90, flex: "0 0 auto" }}>
                  <ConditionBadge condition={row.condition} graded={row.is_graded}
                                  grade={row.grade} grader={row.grader} />
                </Box>

                <Box sx={{ width: 140, flex: "0 0 auto" }}>
                  <QuantityStepper
                    value={row.quantity}
                    label={row.name}
                    onChange={(quantity) => onQuantity(row, quantity)}
                  />
                </Box>

                <Typography
                  sx={{ width: 110, flex: "0 0 auto", fontSize: 12, color: "text.secondary" }}
                >
                  {row.created_at.slice(0, 10)}
                </Typography>
              </Stack>
            );
          })}
        </Box>
      </Box>
    </Stack>
  );
}

/**
 * Condition as a neutral badge with a letter grade — **no colour**.
 *
 * Element already owns hue in this row and rarity owns material. A third encoding competing for
 * attention makes the row unreadable, and colour-coding condition would also mean a red badge for
 * "Damaged", which reads as an error rather than as a fact about a card.
 */
function ConditionBadge({
  condition, graded, grade, grader,
}: { condition: string; graded: boolean; grade: number | null; grader: string | null }) {
  const short: Record<string, string> = {
    mint: "M", near_mint: "NM", lightly_played: "LP",
    moderately_played: "MP", heavily_played: "HP", damaged: "DMG",
  };
  const label = graded && grade !== null ? `${grader ?? "?"} ${grade}` : short[condition] ?? "—";
  const full = graded ? `Graded ${grader ?? ""} ${grade ?? ""}`.trim()
    : condition.replace(/_/g, " ");

  return (
    <Box
      component="span"
      title={full}
      aria-label={full}
      sx={{
        display: "inline-block", px: 0.75, py: 0.25, borderRadius: 0.5,
        border: 1, borderColor: "divider", fontSize: 11, fontWeight: 600,
        color: "text.secondary",
      }}
    >
      {label}
    </Box>
  );
}
