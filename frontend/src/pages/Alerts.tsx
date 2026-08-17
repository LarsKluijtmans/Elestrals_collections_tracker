import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Switch, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { env } from "../env";
import { pricesApi, type PriceAlert } from "../api/prices";
import { formatMoney } from "../components/MoneyFigure";

/**
 * `/alerts` — story 034.
 *
 * The page says what an alert will and will not do, because both are surprising if you have used
 * one of these before:
 *
 * * **Nothing fires on thin data.** Under ADR-004 a lot of what we see is single-source or derived
 *   from asking prices, and firing on that would train people to ignore alerts — at which point the
 *   ones that matter get ignored too.
 * * **A crossing notifies once**, not on every evaluation while a price wobbles over a threshold.
 *
 * Deactivating keeps the threshold; deleting throws it away. Both are offered because they are
 * different intentions, and collapsing them means somebody loses a number they thought about.
 */
export function AlertsPage() {
  const { getAccessToken } = useAuth();
  const client = useQueryClient();

  const alerts = useQuery({
    queryKey: ["alerts"],
    queryFn: () => pricesApi.alerts(getAccessToken),
  });

  const toggle = useMutation({
    mutationFn: async ({ id, active }: { id: string; active: boolean }) => {
      const token = await getAccessToken();
      await fetch(`${env.backendUrl}/api/v1/alerts/${id}?active=${active}`, {
        method: "PATCH",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const remove = useMutation({
    mutationFn: async (id: string) => {
      const token = await getAccessToken();
      await fetch(`${env.backendUrl}/api/v1/alerts/${id}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["alerts"] }),
  });

  if (alerts.isLoading) return <CircularProgress />;
  if (alerts.isError) {
    return <Alert severity="error">{(alerts.error as Error).message}</Alert>;
  }

  const rows = alerts.data ?? [];

  return (
    <Stack sx={{ gap: 3, maxWidth: 860 }}>
      <Box>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>Price alerts</Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
          Tell us a price and we will tell you when a card reaches it.
        </Typography>
      </Box>

      {rows.length === 0 ? (
        <Stack sx={{ gap: 2, p: 6, alignItems: "center", textAlign: "center" }}>
          <Typography sx={{ fontSize: 18, fontWeight: 600 }}>No alerts yet.</Typography>
          <Typography sx={{ fontSize: 14, color: "text.secondary", maxWidth: 440 }}>
            Open a card and set a threshold — above or below — and it will show up here.
          </Typography>
          <Button component={Link} to="/sets" variant="outlined">Browse sets</Button>
        </Stack>
      ) : (
        <Stack sx={{ gap: 1 }}>
          {rows.map((alert) => (
            <AlertRow
              key={alert.id}
              alert={alert}
              onToggle={(active) => toggle.mutate({ id: alert.id, active })}
              onDelete={() => remove.mutate(alert.id)}
            />
          ))}
        </Stack>
      )}

      <Alert severity="info" variant="outlined">
        Alerts only fire on prices we are reasonably confident in — at least a few sales from more
        than one source. A card nobody has been seen selling will not trigger one, however far its
        asking prices move. And a crossing notifies you <strong>once</strong>, not every day a
        price hovers around your number.
      </Alert>
    </Stack>
  );
}

function AlertRow({
  alert, onToggle, onDelete,
}: { alert: PriceAlert; onToggle: (active: boolean) => void; onDelete: () => void }) {
  const cooling =
    alert.cooldown_until !== null && new Date(alert.cooldown_until) > new Date();

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" sx={{ gap: 2, alignItems: "center", flexWrap: "wrap" }}>
        <Box sx={{ flex: 1, minWidth: 200 }}>
          <Typography
            component={Link}
            to={`/cards/${alert.card_id}`}
            sx={{ fontWeight: 600, color: "inherit", display: "block" }}
          >
            {alert.name}
          </Typography>
          <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
            {alert.set_code} · notify when {alert.direction}{" "}
            {formatMoney(alert.threshold_cents, alert.currency)}
          </Typography>
        </Box>

        {cooling ? (
          <Chip size="small" variant="outlined" label="recently fired" />
        ) : alert.last_fired_at ? (
          <Chip size="small" variant="outlined" color="success" label="fired" />
        ) : null}

        <Switch
          checked={alert.is_active}
          onChange={(event) => onToggle(event.target.checked)}
          slotProps={{ input: { "aria-label": `Alert active for ${alert.name}` } }}
        />
        <Button size="small" color="error" onClick={onDelete}>Delete</Button>
      </Stack>
    </Paper>
  );
}
