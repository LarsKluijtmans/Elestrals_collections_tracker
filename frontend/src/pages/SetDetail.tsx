// /sets/:code — the checklist. Public: works signed out.
import { Alert, Box, Chip, Skeleton, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { Link as RouterLink, useParams } from "react-router-dom";
import { fetchSetChecklist } from "../api/backend";
import { ElementChip } from "../components/ElementChip";
import { RarityBadge } from "../components/RarityBadge";

export function SetDetailPage() {
  const { code = "" } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["set", code],
    queryFn: () => fetchSetChecklist(code),
    staleTime: 5 * 60_000,
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

      {total === 0 ? (
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
