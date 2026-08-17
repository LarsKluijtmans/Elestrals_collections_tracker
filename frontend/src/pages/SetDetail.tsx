// /sets/:code — the checklist. Public: works signed out.
//
// Signed in, it also answers story 024's question — *what am I missing from this set* — behind a
// toggle. The definition matters and is enforced server-side: **missing is per card, not per
// printing.** Owning the common version means you have the card, even without the holo, and the
// opposite reading would put this view permanently at odds with the completion ring.
import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, Chip, Skeleton, Stack, ToggleButton, ToggleButtonGroup, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { fetchMissing, fetchSetChecklist } from "../api/backend";
import { downloadCsv, toCsv } from "../collection/csv";
import { ElementChip } from "../components/ElementChip";
import { RarityBadge } from "../components/RarityBadge";

export function SetDetailPage() {
  const { code = "" } = useParams();
  const { isAuthenticated, getAccessToken } = useAuth();
  const [view, setView] = useState<"all" | "missing">("all");

  const { data, isLoading, error } = useQuery({
    queryKey: ["set", code],
    queryFn: () => fetchSetChecklist(code),
    staleTime: 5 * 60_000,
  });

  const missingQuery = useQuery({
    queryKey: ["set", code, "missing"],
    queryFn: () => fetchMissing(code, getAccessToken),
    // Only for a signed-in visitor, and only once they ask: "what am I missing" is meaningless
    // signed out, and fetching it anyway would 401 on every anonymous checklist view.
    enabled: isAuthenticated && view === "missing",
  });

  if (isLoading) return <Skeleton variant="rounded" height={320} />;
  if (error || !data) return <Alert severity="error">Could not load this set.</Alert>;

  const { set, items, total } = data;
  const missing = Math.max(0, set.card_count - set.imported_count);

  return (
    <Stack sx={{ gap: 3 }}>
      <Box>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>
          {set.name}
        </Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
          {set.code}
          {set.series ? ` · ${set.series}` : ""} · {set.imported_count} of {set.card_count} cards
        </Typography>
      </Box>

      {missing > 0 && (
        // Stated plainly rather than hidden. A checklist that silently renumbered itself to
        // what we hold would look complete while missing a third of the set.
        <Alert severity="warning">
          {missing} card{missing === 1 ? "" : "s"} of this set are not in the catalog yet.
          The checklist below shows what has been imported.
        </Alert>
      )}

      {isAuthenticated ? (
        <Stack direction="row" sx={{ gap: 2, alignItems: "center", flexWrap: "wrap" }}>
          <ToggleButtonGroup
            size="small"
            exclusive
            value={view}
            onChange={(_, next) => next && setView(next)}
            aria-label="Which cards to show"
          >
            <ToggleButton value="all">All cards</ToggleButton>
            <ToggleButton value="missing">Missing only</ToggleButton>
          </ToggleButtonGroup>

          {view === "missing" && missingQuery.data ? (
            <>
              <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
                {missingQuery.data.owned_cards} of {missingQuery.data.card_count} owned ·{" "}
                {missingQuery.data.missing.length} missing
              </Typography>
              <Button
                size="small"
                onClick={() => downloadCsv(
                  // The importer's own columns, so this file round-trips: export the gaps, fill
                  // them in a spreadsheet as you buy them, import it back.
                  toCsv(missingQuery.data!.missing.map((card) => ({
                    set_code: set.code,
                    collector_number: card.collector_number,
                    name: card.name,
                    rarity: card.rarity ?? "",
                    quantity: 1,
                  }))),
                  `${set.code}-missing.csv`,
                )}
              >
                Export missing
              </Button>
            </>
          ) : null}
        </Stack>
      ) : null}

      {view === "missing" ? (
        <MissingList query={missingQuery} />
      ) : total === 0 ? (
        <Typography sx={{ color: "text.disabled" }}>No cards imported for this set yet.</Typography>
      ) : (
        <Stack sx={{ gap: 1 }}>
          {items.map((entry) => (
            <Box
              key={entry.card_id}
              component={RouterLink}
              to={`/cards/${entry.card_id}`}
              sx={{
                display: "flex", alignItems: "center", gap: 1.5,
                px: 2, py: 1.25, borderRadius: 1.5, textDecoration: "none",
                color: "inherit", border: 1, borderColor: "divider",
                "&:hover": { bgcolor: "action.hover" },
              }}
            >
              <Typography sx={{ fontSize: 12, color: "text.disabled", minWidth: 72 }}>
                {entry.collector_number}
              </Typography>
              <Typography sx={{ fontSize: 14, fontWeight: 600, flexGrow: 1 }} noWrap>
                {entry.name}
              </Typography>
              <ElementChip element={entry.element} size="xs" />
              {entry.printings.slice(0, 3).map((p) => (
                <RarityBadge key={p.printing_id} rarity={p.rarity} element={entry.element} />
              ))}
              {entry.printings.length > 3 && (
                <Chip size="small" label={`+${entry.printings.length - 3}`} />
              )}
            </Box>
          ))}
        </Stack>
      )}
    </Stack>
  );
}

/**
 * The missing list — and its two very different empty states.
 *
 * A set you have completed and a set the catalog has not imported both render "nothing to show"
 * if you are careless, and they are opposite facts. One is an achievement; the other is our data
 * being incomplete.
 */
function MissingList({
  query,
}: {
  query: { data?: { missing: { card_id: string; collector_number: string; name: string;
                              element: string | null; rarity: string | null }[] };
           isLoading: boolean; isError: boolean };
}) {
  if (query.isLoading) return <Skeleton variant="rounded" height={200} />;
  if (query.isError) return <Alert severity="error">Could not work out what is missing.</Alert>;

  const missing = query.data?.missing ?? [];
  if (!missing.length) {
    return (
      <Alert severity="success">
        You own at least one printing of every card imported for this set.
      </Alert>
    );
  }

  return (
    <Stack sx={{ gap: 1 }}>
      {missing.map((card) => (
        <Box
          key={card.card_id}
          component={RouterLink}
          to={`/cards/${card.card_id}`}
          sx={{
            display: "flex", alignItems: "center", gap: 1.5,
            px: 2, py: 1.25, borderRadius: 1.5, textDecoration: "none",
            color: "inherit", border: 1, borderColor: "divider",
            "&:hover": { bgcolor: "action.hover" },
          }}
        >
          <Typography sx={{ fontSize: 12, color: "text.disabled", minWidth: 72 }}>
            {card.collector_number}
          </Typography>
          <Typography sx={{ fontSize: 14, fontWeight: 600, flexGrow: 1 }} noWrap>
            {card.name}
          </Typography>
          <ElementChip element={card.element} size="xs" />
          {card.rarity ? <RarityBadge rarity={card.rarity} element={card.element} /> : null}
        </Box>
      ))}
    </Stack>
  );
}
