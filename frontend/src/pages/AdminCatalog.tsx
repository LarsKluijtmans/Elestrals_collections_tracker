// /admin/catalog — operator console. RBAC-gated; a non-operator gets 403 from the API.
//
// Answers one question: can I trust what the catalog currently says?
import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Chip, Skeleton, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { fetchCatalogHealth } from "../api/backend";
import { ApiError } from "../api/backend";

const STALENESS_COLOUR = {
  fresh: "success",
  ageing: "warning",
  stale: "error",
  never_run: "default",
} as const;

const STALENESS_LABEL = {
  fresh: "Fresh",
  ageing: "Ageing",
  stale: "Stale",
  never_run: "Never run",
} as const;

export function AdminCatalogPage() {
  const { getAccessToken } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["catalog-health"],
    queryFn: () => fetchCatalogHealth(getAccessToken),
    staleTime: 30_000,
  });

  if (isLoading) return <Skeleton variant="rounded" height={320} />;

  if (error) {
    const forbidden = error instanceof ApiError && error.status === 403;
    return (
      <Alert severity={forbidden ? "warning" : "error"}>
        {forbidden ? "Operator access required." : "Could not load catalog health."}
      </Alert>
    );
  }
  if (!data) return null;

  return (
    <Stack sx={{ gap: 4 }}>
      <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>
        Catalog health
      </Typography>

      <Box>
        <Typography sx={{ fontSize: 20, fontWeight: 650, mb: 1.5 }}>Sources</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Source</TableCell>
              <TableCell>Mode</TableCell>
              <TableCell>Last run</TableCell>
              <TableCell>Freshness</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.sources.map((source) => (
              <TableRow key={source.source}>
                <TableCell>
                  <Typography sx={{ fontSize: 13, fontWeight: 600 }}>
                    {source.display_name}
                  </Typography>
                  <Typography sx={{ fontSize: 11, color: "text.disabled" }}>
                    {source.source}
                  </Typography>
                </TableCell>
                <TableCell sx={{ fontSize: 13 }}>
                  {source.requires_network ? "Network" : "Offline"}
                </TableCell>
                <TableCell sx={{ fontSize: 13 }}>{source.last_status ?? "—"}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color={STALENESS_COLOUR[source.staleness.state]}
                    label={STALENESS_LABEL[source.staleness.state]}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>

      <Box>
        <Typography sx={{ fontSize: 20, fontWeight: 650, mb: 1.5 }}>Coverage</Typography>
        {data.sets_below_coverage.length === 0 ? (
          <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
            Every set matches its declared printed size.
          </Typography>
        ) : (
          <Stack sx={{ gap: 0.75 }}>
            {data.sets_below_coverage.map((set) => (
              <Typography key={set.set_code} sx={{ fontSize: 13 }}>
                <strong>{set.set_code}</strong> — {set.imported} of {set.expected} imported,{" "}
                {set.missing_count} missing
              </Typography>
            ))}
          </Stack>
        )}
      </Box>

      <Box>
        <Typography sx={{ fontSize: 20, fontWeight: 650, mb: 1.5 }}>
          Rejections in the last run
        </Typography>
        {data.rejections.length === 0 ? (
          <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
            Nothing was rejected.
          </Typography>
        ) : (
          <Stack sx={{ gap: 0.75 }}>
            {/* Grouped: "83 × unknown_rarity", not 83 rows. */}
            {data.rejections.map((rejection) => (
              <Typography key={rejection.reason_code} sx={{ fontSize: 13 }}>
                <strong>{rejection.count}</strong> × {rejection.reason_code}{" "}
                <Box component="span" sx={{ color: "text.disabled" }}>
                  (e.g. {rejection.example_source_ref})
                </Box>
              </Typography>
            ))}
          </Stack>
        )}
      </Box>
    </Stack>
  );
}
