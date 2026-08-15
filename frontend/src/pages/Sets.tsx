// /sets — the set gallery. Public: works signed out.
//
// Completion rings render their null state here. Completion is per-user and comes from bolt
// 004's endpoint; it is deliberately not part of the set response, because `/sets` is cached
// and a per-user field in a shared cache serves one collector's data to another.
import { Alert, Box, Card, CardActionArea, Skeleton, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { Link as RouterLink } from "react-router-dom";
import { fetchSets, type SetSummary } from "../api/backend";
import { CompletionRing } from "../components/CompletionRing";

function SetCard({ set }: { set: SetSummary }) {
  const incomplete = set.card_count > 0 && set.imported_count < set.card_count;

  return (
    <Card variant="outlined" sx={{ borderRadius: 2 }}>
      <CardActionArea component={RouterLink} to={`/sets/${set.code}`} sx={{ p: 2.5 }}>
        <Stack direction="row" sx={{ alignItems: "center", gap: 2 }}>
          <Box sx={{ minWidth: 0, flexGrow: 1 }}>
            <Typography sx={{ fontSize: 16, fontWeight: 650, lineHeight: 1.3 }} noWrap>
              {set.name}
            </Typography>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }} noWrap>
              {set.code}
              {set.series ? ` · ${set.series}` : ""}
              {set.released_on ? ` · ${set.released_on}` : ""}
            </Typography>
            <Typography sx={{ fontSize: 12, mt: 0.75, color: incomplete ? "warning.main" : "text.secondary" }}>
              {/* Imported against the *declared printed size*. Saying "1 card" without the
                  denominator is how an incomplete catalog looks finished. */}
              {set.imported_count} of {set.card_count} cards
              {incomplete ? " — catalog incomplete" : ""}
            </Typography>
          </Box>
          {/* null: signed out, or bolt 004 not built yet. Renders the track alone. */}
          <CompletionRing completion={null} />
        </Stack>
      </CardActionArea>
    </Card>
  );
}

export function SetsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sets"],
    queryFn: () => fetchSets(),
    staleTime: 5 * 60_000,
  });

  return (
    <Stack sx={{ gap: 3 }}>
      <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>
        Sets
      </Typography>

      {error && <Alert severity="error">Could not load sets.</Alert>}

      {isLoading && (
        <Stack sx={{ gap: 1.5 }}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} variant="rounded" height={96} />
          ))}
        </Stack>
      )}

      {data && data.items.length === 0 && (
        <Typography sx={{ color: "text.disabled" }}>No sets yet.</Typography>
      )}

      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" },
        }}
      >
        {data?.items.map((set) => <SetCard key={set.code} set={set} />)}
      </Box>
    </Stack>
  );
}
