import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, CircularProgress, MenuItem, Stack, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  adjustInventory, bulkDelete, bulkEdit, countSelection, createSavedView,
  deleteSavedView, fetchCollection, fetchSavedViews,
  type BulkResult, type CollectionRow, type SavedView,
} from "../../api/backend";
import { BulkBar } from "../../collection/BulkBar";
import { CollectionTable } from "../../collection/CollectionTable";
import { FilterRail, type Vocabulary } from "../../collection/FilterRail";
import {
  describeFilters, parseFilters, SORT_LABELS, toSearchParams,
  type Density, type Filters, type Sort,
} from "../../collection/filters";
import { toCsv, downloadCsv } from "../../collection/csv";

/**
 * `/collection` — stories 019, 020, 021, 022.
 *
 * **The URL is the state.** Filters, sort and cursor all live in the query string, so a filtered
 * view is a link you can send someone, the back button behaves, and a reload lands where you were.
 * Story 020 is explicit that retrofitting this means rewriting every filter component.
 *
 * Density is the one thing that is *not* in the URL. It is a preference about how you like to read
 * a table, not a description of what you are looking at — so it persists per browser rather than
 * travelling with a shared link, which would impose your preference on whoever opens it.
 */

const DENSITY_KEY = "elestrals.density";

export function CollectionPage() {
  const { getAccessToken } = useAuth();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();

  const filters = useMemo(() => parseFilters(params), [params]);
  const sort = (params.get("sort") as Sort) || "added_desc";

  const [density, setDensity] = useState<Density>(
    () => (localStorage.getItem(DENSITY_KEY) as Density) || "comfortable",
  );
  const [pages, setPages] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectAllMatching, setSelectAllMatching] = useState(false);
  const [result, setResult] = useState<BulkResult | null>(null);

  const query = toSearchParams(filters, { sort }).toString();

  const collection = useQuery({
    queryKey: ["collection", query, pages],
    queryFn: async () => {
      // Pages accumulate rather than replace: the virtualizer renders one long list, so
      // "load more" appends. Refetching from the first cursor each time would restart the scroll.
      const first = await fetchCollection(query, getAccessToken);
      let items = first.items;
      let cursor = first.next_cursor;
      for (const stored of pages) {
        if (stored !== cursor) break;
        const next = await fetchCollection(`${query}&cursor=${stored}`, getAccessToken);
        items = [...items, ...next.items];
        cursor = next.next_cursor;
      }
      return { ...first, items, next_cursor: cursor };
    },
  });

  const views = useQuery({
    queryKey: ["collection", "views"],
    queryFn: () => fetchSavedViews(getAccessToken),
  });

  const selectionBody = useMemo(
    () => (selectAllMatching ? { filters } : { item_ids: [...selected] }),
    [selectAllMatching, filters, selected],
  );

  const matchingCount = useQuery({
    queryKey: ["collection", "selection", query, selectAllMatching],
    queryFn: () => countSelection({ filters }, getAccessToken),
    enabled: selectAllMatching,
  });

  const selectedCount = selectAllMatching ? (matchingCount.data ?? 0) : selected.size;

  function applyFilters(next: Filters, nextSort: Sort = sort): void {
    setPages([]);
    setSelected(new Set());
    setSelectAllMatching(false);
    setParams(toSearchParams(next, { sort: nextSort }), { replace: false });
  }

  const quantity = useMutation({
    mutationFn: ({ row, next }: { row: CollectionRow; next: number }) =>
      // Delta plus expectation — ADR-005's compare-and-swap. The stepper knows what it believed
      // the quantity was, so it does not need to read the row first.
      adjustInventory(
        row.id, { delta: next - row.quantity, expected_quantity: row.quantity }, getAccessToken,
      ),
    onSettled: () => client.invalidateQueries({ queryKey: ["collection"] }),
  });

  const edit = useMutation({
    mutationFn: (fields: Record<string, unknown>) =>
      bulkEdit({ ...selectionBody, ...fields }, getAccessToken),
    onSuccess: (data) => {
      setResult(data);
      setSelected(new Set());
      setSelectAllMatching(false);
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["collection"] }),
  });

  const remove = useMutation({
    mutationFn: () => bulkDelete(selectionBody, getAccessToken),
    onSuccess: (data) => {
      setResult(data);
      setSelected(new Set());
      setSelectAllMatching(false);
      setPages([]);
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["collection"] }),
  });

  const saveView = useMutation({
    mutationFn: (name: string) =>
      createSavedView({ name, filters, sort, density }, getAccessToken),
    onSettled: () => client.invalidateQueries({ queryKey: ["collection", "views"] }),
  });

  const dropView = useMutation({
    mutationFn: (id: string) => deleteSavedView(id, getAccessToken),
    onSettled: () => client.invalidateQueries({ queryKey: ["collection", "views"] }),
  });

  const rows = collection.data?.items ?? [];
  const total = collection.data?.total ?? 0;

  const loadMore = useCallback(() => {
    const cursor = collection.data?.next_cursor;
    if (cursor && !pages.includes(cursor)) setPages((current) => [...current, cursor]);
  }, [collection.data?.next_cursor, pages]);

  // Built from what is loaded rather than from a separate endpoint. It narrows as you filter,
  // which is the behaviour you want: options that would return nothing stop being offered.
  const vocabulary = useMemo<Vocabulary>(() => {
    const collect = (get: (row: CollectionRow) => string | null) =>
      [...new Set(rows.map(get).filter((v): v is string => Boolean(v)))].sort();
    return {
      set_code: collect((r) => r.set_code),
      element: collect((r) => r.element),
      rarity: collect((r) => r.rarity),
      condition: collect((r) => r.condition),
      finish: collect((r) => r.finish),
      language: collect((r) => r.language),
    };
  }, [rows]);

  function applyView(view: SavedView): void {
    setDensity(view.density as Density);
    localStorage.setItem(DENSITY_KEY, view.density);
    applyFilters(parseFilters(new URLSearchParams(
      Object.entries(view.filters).flatMap(([key, value]) =>
        Array.isArray(value) ? value.map((v) => [key, String(v)] as [string, string])
          : [[key, String(value)] as [string, string]],
      ),
    )), view.sort as Sort);
  }

  if (collection.isLoading) return <CircularProgress />;

  if (collection.isError) {
    return <Alert severity="error">{(collection.error as Error).message}</Alert>;
  }

  return (
    <Stack sx={{ gap: 2 }}>
      <Stack direction="row" sx={{ gap: 2, alignItems: "center", flexWrap: "wrap" }}>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>Collection</Typography>
        <Button component={Link} to="/collection/add" variant="contained" size="small">
          Add cards
        </Button>

        <TextField
          select size="small" label="Sort" value={sort} sx={{ ml: "auto", minWidth: 160 }}
          onChange={(event) => applyFilters(filters, event.target.value as Sort)}
        >
          {Object.entries(SORT_LABELS).map(([value, label]) => (
            <MenuItem key={value} value={value}>{label}</MenuItem>
          ))}
        </TextField>

        <TextField
          select size="small" label="Density" value={density} sx={{ minWidth: 150 }}
          onChange={(event) => {
            const next = event.target.value as Density;
            setDensity(next);
            // Persisted across sessions, per story 019 — and per browser, not per link.
            localStorage.setItem(DENSITY_KEY, next);
          }}
        >
          <MenuItem value="comfortable">Comfortable</MenuItem>
          <MenuItem value="compact">Compact</MenuItem>
        </TextField>
      </Stack>

      <Stack direction={{ xs: "column", md: "row" }} sx={{ gap: 3, alignItems: "flex-start" }}>
        <FilterRail
          filters={filters}
          vocabulary={vocabulary}
          total={total}
          views={views.data ?? []}
          onChange={(next) => applyFilters(next)}
          onClear={() => applyFilters({})}
          onSaveView={(name) => saveView.mutate(name)}
          onDeleteView={(id) => dropView.mutate(id)}
          onApplyView={applyView}
        />

        <Stack sx={{ flex: 1, minWidth: 0 }}>
          <BulkBar
            count={selectedCount}
            busy={edit.isPending || remove.isPending}
            result={result}
            onEdit={(fields) => edit.mutate(fields)}
            onDelete={() => remove.mutate()}
            onExport={() => downloadCsv(
              toCsv(rows.filter((r) => selectAllMatching || selected.has(r.id))),
              "elestrals-selection.csv",
            )}
            onClear={() => { setSelected(new Set()); setSelectAllMatching(false); }}
            onDismissResult={() => setResult(null)}
          />

          {selected.size > 0 && selected.size === rows.length && !selectAllMatching
            && total > rows.length ? (
            // Select-all only reaches what is loaded; this is the offer to make it mean the
            // filter instead. Story 022: select-all respects the active filter and says how many.
            <Alert severity="info" sx={{ mb: 1 }} action={
              <Button size="small" onClick={() => setSelectAllMatching(true)}>
                Select all {total.toLocaleString()}
              </Button>
            }>
              All {rows.length} loaded rows are selected.
            </Alert>
          ) : null}

          {rows.length === 0 ? (
            <EmptyState filters={filters} onClear={() => applyFilters({})} />
          ) : (
            <CollectionTable
              rows={rows}
              density={density}
              sort={sort}
              selected={selected}
              allSelected={selectAllMatching || (rows.length > 0 && selected.size === rows.length)}
              loading={collection.isFetching}
              onSort={(next) => applyFilters(filters, next)}
              onToggle={(id) => setSelected((current) => {
                const next = new Set(current);
                if (next.has(id)) next.delete(id);
                else next.add(id);
                setSelectAllMatching(false);
                return next;
              })}
              onToggleAll={() => {
                setSelectAllMatching(false);
                setSelected((current) =>
                  current.size === rows.length ? new Set() : new Set(rows.map((r) => r.id)),
                );
              }}
              onQuantity={(row, next) => quantity.mutate({ row, next })}
              onReachEnd={loadMore}
            />
          )}

          {collection.isFetching ? (
            <Box sx={{ p: 2, textAlign: "center" }}><CircularProgress size={20} /></Box>
          ) : null}
        </Stack>
      </Stack>
    </Stack>
  );
}

/**
 * Two different facts need two different screens.
 *
 * "You own nothing yet" is an onboarding moment and gets an action. "Nothing matches these
 * filters" is a dead end and gets a way out — naming the filters, because "No results" leaves a
 * collector unable to tell which of the two situations they are in.
 */
function EmptyState({ filters, onClear }: { filters: Filters; onClear: () => void }) {
  const described = describeFilters(filters);

  if (!described) {
    return (
      <Stack sx={{ gap: 2, p: 6, alignItems: "center", textAlign: "center" }}>
        <Typography sx={{ fontSize: 18, fontWeight: 600 }}>
          Your collection is empty.
        </Typography>
        <Typography sx={{ fontSize: 14, color: "text.secondary", maxWidth: 420 }}>
          Add cards by typing a name, or work through a whole set at once. Most people start with
          the set they opened most recently.
        </Typography>
        <Button component={Link} to="/collection/add" variant="contained">Add your first card</Button>
      </Stack>
    );
  }

  return (
    <Stack sx={{ gap: 2, p: 6, alignItems: "center", textAlign: "center" }}>
      <Typography sx={{ fontSize: 16, fontWeight: 600 }}>
        No cards match {described}.
      </Typography>
      <Button onClick={onClear} variant="outlined">Clear all filters</Button>
    </Stack>
  );
}
