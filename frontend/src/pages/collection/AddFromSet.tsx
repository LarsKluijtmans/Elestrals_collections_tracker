import { Alert, Skeleton, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { fetchSetChecklist } from "../../api/backend";
import { CarriedDefaultsBar } from "../../components/add/CarriedDefaultsBar";
import { LiveAnnouncer } from "../../components/add/LiveAnnouncer";
import { SessionTally } from "../../components/add/SessionTally";
import { SetGrid } from "../../components/add/SetGrid";

/**
 * `/collection/add/set/:setCode` — grid entry after a box opening.
 *
 * Shares the session with `/collection/add`: the same carried condition, the same tally, the same
 * undo stack. That is why the provider sits above the router rather than inside either page — a
 * collector who sets Foil here and then switches to search entry should not have to set it again.
 */
export function AddFromSetPage() {
  const { setCode = "" } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["set-checklist", setCode],
    queryFn: () => fetchSetChecklist(setCode),
    staleTime: 5 * 60_000,
  });

  return (
    <Stack sx={{ gap: 3 }}>
      <LiveAnnouncer />

      <Stack sx={{ gap: 0.5 }}>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>
          {data?.set.name ?? setCode}
        </Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
          Click a card to add one. Shift-click to remove one.
        </Typography>
      </Stack>

      <CarriedDefaultsBar />

      <Stack direction={{ xs: "column", md: "row" }} sx={{ gap: 3, alignItems: "flex-start" }}>
        <Stack sx={{ flex: 1, minWidth: 0 }}>
          {isLoading && <Skeleton variant="rounded" height={420} />}
          {error && <Alert severity="error">Could not load this set.</Alert>}
          {data && data.items.length === 0 && (
            <Alert severity="info">
              This set has no cards in the catalog yet, so there is nothing to click.
            </Alert>
          )}
          {data && data.items.length > 0 && <SetGrid entries={data.items} />}
        </Stack>
        <SessionTally />
      </Stack>
    </Stack>
  );
}
