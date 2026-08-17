import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, Chip, CircularProgress, MenuItem, Paper, Stack, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchInbox, fetchNotificationPreferences, sendTestNotification,
  setNotificationPreference,
} from "../api/backend";

/**
 * `/settings/notifications` — story 032.
 *
 * The defaults are conservative and the page says so, because "we will not email you unless you
 * ask" is a promise worth making visibly rather than one buried in a settings default. A product
 * that mails people by default is a product people mute, and a muted channel is worse than no
 * channel — it looks like it works.
 *
 * `account` is deliberately not settable to "none". A deletion confirmation is not marketing, and
 * somebody who turned everything off still needs to be told their account is going away.
 */

const EVENTS: { key: string; label: string; description: string; locked?: boolean }[] = [
  {
    key: "account",
    label: "Account",
    description: "Deletion confirmations and anything else you genuinely need to know.",
    locked: true,
  },
  {
    key: "price_alert",
    label: "Price alerts",
    description: "When a card on your wishlist reaches the price you set. Phase 2.",
  },
  {
    key: "import_finished",
    label: "Import finished",
    description: "When a large CSV import completes.",
  },
  {
    key: "wishlist_match",
    label: "Wishlist matches",
    description: "When something on your wishlist becomes available.",
  },
];

const CHANNELS = [
  { value: "none", label: "Don’t notify me" },
  { value: "email", label: "Email" },
  { value: "inapp", label: "In-app inbox" },
  { value: "push", label: "Push" },
];

export function NotificationSettingsPage() {
  const { getAccessToken } = useAuth();
  const client = useQueryClient();

  const preferences = useQuery({
    queryKey: ["notifications", "preferences"],
    queryFn: () => fetchNotificationPreferences(getAccessToken),
  });

  const inbox = useQuery({
    queryKey: ["notifications", "inbox"],
    queryFn: () => fetchInbox(getAccessToken),
  });

  const update = useMutation({
    mutationFn: ({ event, channel }: { event: string; channel: string }) =>
      setNotificationPreference(event, channel, getAccessToken),
    onSettled: () => client.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const test = useMutation({
    mutationFn: (channel: string) => sendTestNotification(channel, getAccessToken),
    onSettled: () => client.invalidateQueries({ queryKey: ["notifications", "inbox"] }),
  });

  if (preferences.isLoading) return <CircularProgress />;
  if (preferences.isError) {
    return <Alert severity="error">{(preferences.error as Error).message}</Alert>;
  }

  const prefs = preferences.data!;

  return (
    <Stack sx={{ gap: 3, maxWidth: 760 }}>
      <Box>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>Notifications</Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
          Everything except account messages starts turned off. We will not contact you about
          anything you have not asked for.
        </Typography>
      </Box>

      <Stack sx={{ gap: 1.5 }}>
        {EVENTS.map((event) => (
          <Paper key={event.key} variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" sx={{ gap: 2, alignItems: "center", flexWrap: "wrap" }}>
              <Box sx={{ flex: 1, minWidth: 220 }}>
                <Typography sx={{ fontWeight: 600 }}>{event.label}</Typography>
                <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
                  {event.description}
                </Typography>
              </Box>

              <TextField
                select
                size="small"
                label="Channel"
                sx={{ minWidth: 180 }}
                value={prefs[event.key] ?? "none"}
                onChange={(e) => update.mutate({ event: event.key, channel: e.target.value })}
              >
                {CHANNELS
                  // `account` cannot be silenced — the option is not offered rather than offered
                  // and rejected, so nobody discovers the rule by hitting an error.
                  .filter((c) => !(event.locked && c.value === "none"))
                  .map((channel) => (
                    <MenuItem key={channel.value} value={channel.value}>{channel.label}</MenuItem>
                  ))}
              </TextField>
            </Stack>
          </Paper>
        ))}
      </Stack>

      {update.isError ? (
        <Alert severity="warning">{(update.error as Error).message}</Alert>
      ) : null}

      <Box>
        <Button
          variant="outlined"
          disabled={test.isPending}
          onClick={() => test.mutate(prefs.account === "none" ? "email" : prefs.account)}
        >
          Send a test
        </Button>
        <Typography sx={{ fontSize: 12, color: "text.disabled", mt: 1 }}>
          {/* Queued, not sent inline — and that is the point. The test takes the same path a real
              notification takes, so one that arrives proves the whole chain including the outbox,
              and one that does not leaves a row an operator can look at. */}
          The test is queued the same way every notification is. If delivery is down it will wait
          and arrive when the service recovers, rather than being lost.
        </Typography>
      </Box>

      {inbox.data?.items.length ? (
        <Box>
          <Typography variant="overline" color="text.disabled">Recent notifications</Typography>
          <Stack sx={{ gap: 0.5, mt: 1 }}>
            {inbox.data.items.slice(0, 10).map((entry) => (
              <Stack
                key={entry.id}
                direction="row"
                sx={{ gap: 2, alignItems: "center", flexWrap: "wrap" }}
              >
                <Typography sx={{ fontSize: 13, flex: 1, minWidth: 200 }}>
                  {entry.subject}
                </Typography>
                <Chip
                  size="small"
                  variant="outlined"
                  color={
                    entry.status === "sent" ? "success"
                      : entry.status === "dead" ? "error" : "default"
                  }
                  label={entry.status === "pending" && entry.attempts
                    ? `retrying (${entry.attempts})`
                    : entry.status}
                />
                <Typography sx={{ fontSize: 11, color: "text.disabled" }}>
                  {entry.created_at.slice(0, 10)}
                </Typography>
              </Stack>
            ))}
          </Stack>
          {inbox.data.pending ? (
            <Typography sx={{ fontSize: 12, color: "text.secondary", mt: 1 }}>
              {inbox.data.pending} waiting to be delivered.
            </Typography>
          ) : null}
        </Box>
      ) : null}
    </Stack>
  );
}
