import { Box, List, ListItemButton, Paper, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useRef, useState } from "react";
import { searchCards, type CardSearchResult } from "../../api/backend";
import { useAddSession } from "../../session/AddSessionContext";

const DEBOUNCE_MS = 120;
const MIN_TERM = 3;

/**
 * The keyboard contract. This is the single interaction the product is judged on: a collector
 * who finds it slow does not come back, and no other feature compensates.
 *
 *   (load)        focus is already here — no click needed to start
 *   type          debounced 120ms, previous request aborted
 *   ↓ / ↑         move the highlight; the list never takes focus
 *   Enter         add the highlighted printing, clear, refocus
 *   Esc           clear, keep focus
 *   Ctrl/Cmd+Z    undo the last add — only when the field is empty
 *
 * Two of those are easy to get wrong and both are load-bearing:
 *
 * **`Enter` with a search in flight waits for it.** Acting on the previous result set would add
 * the wrong card, silently, at speed. A visible pause is the lesser failure by a wide margin.
 *
 * **`Ctrl+Z` fires only when the field is empty**, so it does not fight the browser's own text
 * undo while somebody is correcting a typo.
 */
export function AddSearchBox() {
  const { add, undoLast, carried } = useAddSession();
  const [term, setTerm] = useState("");
  const [results, setResults] = useState<CardSearchResult[]>([]);
  const [highlight, setHighlight] = useState(0);
  const [searching, setSearching] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // The in-flight promise, so `Enter` can await the answer instead of acting on stale rows.
  const inFlight = useRef<Promise<CardSearchResult[]> | null>(null);

  useEffect(() => {
    if (term.trim().length < MIN_TERM) {
      setResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    const timer = setTimeout(() => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const promise = searchCards(term.trim(), {}, 12)
        .then((page) => {
          if (controller.signal.aborted) return results;
          setResults(page.items);
          setHighlight(0);
          setSearching(false);
          return page.items;
        })
        .catch(() => {
          if (!controller.signal.aborted) setSearching(false);
          return [];
        });
      inFlight.current = promise;
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
    // `results` is deliberately not a dependency: including it would restart the search on its
    // own result and loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [term]);

  async function commit(): Promise<void> {
    // Await an in-flight search rather than acting on what is currently on screen.
    const rows = searching && inFlight.current ? await inFlight.current : results;
    const chosen = rows[highlight];
    if (!chosen) return; // Enter with no results does nothing — no error flash, focus retained

    const printing = chosen.primary_printing;
    if (!printing) return;

    void add({
      printingId: printing.printing_id,
      label: {
        name: chosen.name,
        setCode: chosen.set_code,
        collectorNumber: chosen.collector_number,
        finish: printing.finish,
      },
    });

    setTerm("");
    setResults([]);
    setHighlight(0);
    inputRef.current?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>): void {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((current) => Math.min(current + 1, Math.max(results.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      void commit();
    } else if (event.key === "Escape") {
      setTerm("");
      setResults([]);
    } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
      // Only when empty, so native text undo still works while correcting a typo.
      if (term === "") {
        event.preventDefault();
        void undoLast();
      }
    }
  }

  return (
    <Stack sx={{ gap: 1 }}>
      <TextField
        inputRef={inputRef}
        // Focus is already here on load. A collector with a box on the desk should not have to
        // click anything to start.
        autoFocus
        fullWidth
        value={term}
        onChange={(event) => setTerm(event.target.value)}
        onKeyDown={onKeyDown}
        label={`Add a card as ${carried.condition.replace("_", " ")} · ${carried.finish}`}
        placeholder="Type a card name…"
        // Browsers will offer a street address in a card search otherwise. Pure noise.
        autoComplete="off"
        slotProps={{
          htmlInput: {
            "aria-autocomplete": "list",
            "aria-controls": "add-results",
            "aria-activedescendant": results[highlight]
              ? `add-result-${results[highlight].card_id}`
              : undefined,
            role: "combobox",
            "aria-expanded": results.length > 0,
          },
        }}
      />

      {results.length > 0 && (
        <Paper variant="outlined">
          <List id="add-results" role="listbox" dense>
            {results.map((result, index) => (
              <ListItemButton
                key={result.card_id}
                id={`add-result-${result.card_id}`}
                role="option"
                aria-selected={index === highlight}
                selected={index === highlight}
                // Mouse users get the same path; the highlight follows the pointer so `Enter`
                // and a click never disagree about which row is "the" row.
                onMouseEnter={() => setHighlight(index)}
                onClick={() => void commit()}
              >
                <Stack direction="row" sx={{ gap: 2, alignItems: "baseline", width: "100%" }}>
                  <Typography sx={{ fontWeight: 600 }}>{result.name}</Typography>
                  <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
                    {result.set_code} {result.collector_number}
                  </Typography>
                  {result.printing_count > 1 && (
                    <Typography sx={{ fontSize: 12, color: "text.disabled", ml: "auto" }}>
                      {result.printing_count} printings
                    </Typography>
                  )}
                </Stack>
              </ListItemButton>
            ))}
          </List>
        </Paper>
      )}

      {term.trim().length >= MIN_TERM && !searching && results.length === 0 && (
        // A calm empty state, not an error. Somebody pasting a 40-character string has not done
        // anything wrong.
        <Box sx={{ px: 1 }}>
          <Typography sx={{ fontSize: 13, color: "text.disabled" }}>
            No cards match “{term.trim()}”.
          </Typography>
        </Box>
      )}
    </Stack>
  );
}
