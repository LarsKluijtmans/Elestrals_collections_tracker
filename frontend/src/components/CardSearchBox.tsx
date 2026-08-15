// Ranked card search with a keyboard-only path.
//
// This component is the contract bolt 005's fast-add flow consumes. ux-guide §12 makes that
// flow one of the two interactions worth over-investing in: three characters → arrow → Enter,
// under five seconds, hands never leaving the keyboard. Specified and built here so bolt 005
// consumes it rather than reworking it.
//
// It deliberately does not know what selection *means*. It emits `onSelect(result)`; the page
// decides whether that navigates or adds a card.
import { Box, CircularProgress, InputBase, Paper, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  searchCards,
  type CardSearchResult,
  type SearchFilters,
} from "../api/backend";
import { ElementChip } from "./ElementChip";
import { RarityBadge } from "./RarityBadge";

/** Matches the backend's MIN_TERM_LENGTH: below this it returns an empty page without querying. */
const MIN_TERM = 2;
const DEBOUNCE_MS = 180;

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

export function CardSearchBox({
  onSelect,
  filters,
  placeholder = "Search cards…",
  autoFocus = false,
  limit = 12,
}: {
  onSelect: (result: CardSearchResult) => void;
  filters?: SearchFilters;
  placeholder?: string;
  autoFocus?: boolean;
  limit?: number;
}) {
  const [term, setTerm] = useState("");
  const [active, setActive] = useState(-1);
  const debounced = useDebounced(term, DEBOUNCE_MS);
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const filterKey = useMemo(() => JSON.stringify(filters ?? {}), [filters]);

  // Keyed on the *debounced* term, so an in-flight response for a stale prefix can never
  // overwrite a newer one — the classic search-as-you-type race.
  const { data, isFetching } = useQuery({
    queryKey: ["cards", debounced, filterKey, limit],
    queryFn: () => searchCards(debounced, filters ?? {}, limit),
    enabled: debounced.trim().length >= MIN_TERM,
    staleTime: 60_000,
  });

  const items = data?.items ?? [];

  // Reset the cursor whenever the result set changes; keeping an index across different
  // results is how Enter commits a row the user never looked at.
  useEffect(() => {
    setActive(items.length > 0 ? 0 : -1);
  }, [data]);

  function commit(index: number) {
    const chosen = items[index] ?? items[0];
    if (chosen) onSelect(chosen);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      // Clamp rather than wrap: silently jumping from the last row back to the first is how
      // someone adds the wrong card while looking at the keyboard, not the screen.
      setActive((i) => Math.min(i + 1, items.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      commit(active);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setTerm("");
      setActive(-1);
      inputRef.current?.focus(); // keep focus: the next card is coming
    }
  }

  const showList = debounced.trim().length >= MIN_TERM;

  return (
    <Box sx={{ position: "relative", width: "100%" }}>
      <Paper
        variant="outlined"
        sx={{ display: "flex", alignItems: "center", gap: 1.5, px: 2, py: 1, borderRadius: 2 }}
      >
        <Search size={16} aria-hidden />
        <InputBase
          inputRef={inputRef}
          value={term}
          autoFocus={autoFocus}
          placeholder={placeholder}
          onChange={(e) => setTerm(e.target.value)}
          onKeyDown={onKeyDown}
          sx={{ flexGrow: 1, fontSize: 14 }}
          inputProps={{
            "aria-label": "Search cards",
            role: "combobox",
            "aria-expanded": showList,
            "aria-controls": listId,
            "aria-autocomplete": "list",
            ...(active >= 0 && items[active]
              ? { "aria-activedescendant": `${listId}-${items[active].card_id}` }
              : {}),
          }}
        />
        {isFetching && <CircularProgress size={14} />}
      </Paper>

      {showList && (
        <Paper
          variant="outlined"
          id={listId}
          role="listbox"
          aria-label="Search results"
          sx={{
            position: "absolute", zIndex: 10, mt: 1, width: "100%",
            maxHeight: 380, overflowY: "auto", borderRadius: 2,
          }}
        >
          {items.length === 0 && !isFetching && (
            <Typography sx={{ p: 2, fontSize: 13, color: "text.disabled" }}>
              No cards found
            </Typography>
          )}

          {items.map((item, index) => (
            <Box
              key={item.card_id}
              id={`${listId}-${item.card_id}`}
              role="option"
              aria-selected={index === active}
              onMouseEnter={() => setActive(index)}
              onClick={() => commit(index)}
              sx={{
                display: "flex", alignItems: "center", gap: 1.5,
                px: 2, py: 1.25, cursor: "pointer",
                bgcolor: index === active ? "action.selected" : "transparent",
              }}
            >
              <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                <Typography sx={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3 }} noWrap>
                  {item.name}
                </Typography>
                <Typography sx={{ fontSize: 12, color: "text.secondary" }} noWrap>
                  {item.set_code} · {item.collector_number}
                  {item.printing_count > 1 && ` · ${item.printing_count} printings`}
                </Typography>
              </Box>
              <ElementChip element={item.element} size="xs" />
              {item.primary_printing && (
                <RarityBadge rarity={item.primary_printing.rarity} element={item.element} />
              )}
            </Box>
          ))}
        </Paper>
      )}
    </Box>
  );
}
