import {
  Alert, Box, CircularProgress, Paper, Stack, Table, TableBody, TableCell, TableHead,
  TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { Link as RouterLink } from "react-router-dom";
import { pricesApi, type Mover } from "../api/prices";
import { formatMoney } from "../components/MoneyFigure";

/**
 * `/prices` — the public market overview.
 *
 * `min_observations` comes back in the response and is displayed, because it is the difference
 * between a market overview and a noise generator: without it the list is dominated by printings
 * with one sale each, which is the data least worth ranking presented as the most interesting.
 */
export function PricesPage() {
  const overview = useQuery({
    queryKey: ["prices", "overview"],
    queryFn: () => pricesApi.overview(7),
  });

  if (overview.isLoading) return <CircularProgress />;
  if (overview.isError) {
    return <Alert severity="warning">Market data is unavailable right now.</Alert>;
  }

  const data = overview.data!;
  const empty = data.movers_up.length === 0 && data.movers_down.length === 0;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Market</Typography>
        <Typography variant="body2" color="text.secondary">
          Movers over the last {data.window_days} days, from observed sales. A printing needs at
          least {data.min_observations} observations to appear, so one odd sale cannot top the
          list.
        </Typography>
      </Box>

      {empty ? (
        // Says the market is thinly covered rather than presenting a confident-looking list of
        // noise, which is what lowering the bar would produce.
        <Alert severity="info">
          Not enough sales have been observed yet to rank anything. This section fills in as
          coverage grows.
        </Alert>
      ) : (
        <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
          <MoverTable title="Rising" movers={data.movers_up} />
          <MoverTable title="Falling" movers={data.movers_down} />
        </Stack>
      )}

      {data.priced_as_of ? (
        <Typography variant="caption" color="text.secondary">
          Prices published {new Date(data.priced_as_of).toLocaleString()}
        </Typography>
      ) : null}
    </Stack>
  );
}

function MoverTable({ title, movers }: { title: string; movers: Mover[] }) {
  return (
    <Paper sx={{ flex: 1, p: 2 }}>
      <Typography variant="h6" gutterBottom>{title}</Typography>
      {movers.length === 0 ? (
        <Typography color="text.secondary">Nothing qualifies yet.</Typography>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Printing</TableCell>
              <TableCell align="right">Was</TableCell>
              <TableCell align="right">Now</TableCell>
              <TableCell align="right">Change</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {movers.map((mover) => (
              <TableRow key={mover.printing_id} hover>
                <TableCell>
                  <RouterLink to={`/cards/${mover.printing_id}`}>
                    {mover.printing_id.slice(0, 8)}…
                  </RouterLink>
                </TableCell>
                <TableCell align="right">{formatMoney(mover.from_cents, "EUR")}</TableCell>
                <TableCell align="right">{formatMoney(mover.to_cents, "EUR")}</TableCell>
                <TableCell align="right">
                  {mover.change_pct > 0 ? "+" : ""}
                  {mover.change_pct.toFixed(1)}%
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Paper>
  );
}
