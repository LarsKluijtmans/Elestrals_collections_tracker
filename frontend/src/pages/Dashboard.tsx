import { useAuth } from "@lars-kluijtmans/react-auth";
import { Alert, Box, Button, CircularProgress, Paper, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchDashboard, type DashboardData } from "../api/backend";
import { CompletionRing } from "../components/CompletionRing";
import { formatMoney } from "../components/MoneyFigure";
import { ProfileCard } from "../components/ProfileCard";

/**
 * `/dashboard` — story 036.
 *
 * **The empty state is the more important of the two designs**, because it is what every new user
 * sees first. So it is a written onboarding screen with one action, not four tiles reading zero —
 * and `is_empty` comes from the API rather than being inferred from those zeroes, because
 * inferring it is exactly how somebody ninety seconds into signing up gets shown a wall of noughts.
 *
 * **The value tile does not render a zero.** Until intent 002's rollups are publishing for this
 * collection, it reads "Available in phase 2". A zero is a claim — "your collection is worth
 * nothing" — and it is false. The same reasoning is why `collection_snapshots.total_value_cents`
 * is nullable and why the price tab refuses to draw a flat line at zero.
 */
export function DashboardPage() {
  const { getAccessToken } = useAuth();
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => fetchDashboard(getAccessToken),
  });

  if (dashboard.isLoading) return <CircularProgress />;
  if (dashboard.isError) {
    return <Alert severity="error">{(dashboard.error as Error).message}</Alert>;
  }

  const data = dashboard.data!;
  if (data.is_empty) return <Onboarding />;

  return (
    <Stack spacing={5}>
      <Stack direction="row" sx={{ alignItems: "center", gap: 2, flexWrap: "wrap" }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 750, letterSpacing: "-0.025em" }}>
            Your collection
          </Typography>
        </Box>
        {/* Prominent, per story 036 — adding cards is the thing people come here to do. */}
        <Button component={Link} to="/collection/add" variant="contained" sx={{ ml: "auto" }}>
          Add cards
        </Button>
      </Stack>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={3}>
        <Tile label="Cards" value={data.total_items.toLocaleString()} />
        <Tile label="Printings" value={data.distinct_printings.toLocaleString()} />
        <Tile label="Sets started" value={data.sets_started.toLocaleString()} />
        <ValueTile value={data.value} />
      </Stack>

      {data.rings.length ? (
        <Box>
          <Typography variant="overline" color="text.disabled">Closest to complete</Typography>
          <Stack direction="row" spacing={3} sx={{ mt: 1, flexWrap: "wrap" }}>
            {data.rings.map((ring) => (
              <Box key={ring.set_code} component={Link} to={`/sets/${ring.set_code}`}
                   sx={{ textDecoration: "none", color: "inherit" }}>
                <Stack sx={{ alignItems: "center", gap: 0.5 }}>
                  <CompletionRing
                    completion={ring.ratio}
                    size={56}
                    label={`${ring.set_name}: ${ring.owned_cards} of ${ring.card_count}`}
                  />
                  <Typography sx={{ fontSize: 12 }}>{ring.set_code}</Typography>
                  <Typography sx={{ fontSize: 11, color: "text.disabled" }}>
                    {ring.owned_cards}/{ring.card_count}
                  </Typography>
                </Stack>
              </Box>
            ))}
          </Stack>
        </Box>
      ) : null}

      <RecentActivity recent={data.recent} />

      <ProfileCard />
    </Stack>
  );
}

function Onboarding() {
  return (
    <Stack spacing={3} sx={{ maxWidth: 560, py: 6 }}>
      <Typography variant="h4" sx={{ fontWeight: 750, letterSpacing: "-0.025em" }}>
        Let’s get your collection in.
      </Typography>
      <Typography color="text.secondary">
        Two ways to start, and most people use both. Type a card name and press Enter to add one at
        a time — it is built for a box on the desk and a hand on the keyboard. Or open a set and
        click through the grid to record a whole one.
      </Typography>
      <Stack direction="row" spacing={2}>
        <Button component={Link} to="/collection/add" variant="contained" size="large">
          Add your first card
        </Button>
        <Button component={Link} to="/sets" variant="outlined" size="large">
          Browse sets
        </Button>
      </Stack>
      <Typography variant="caption" color="text.disabled">
        Nothing here is public unless you choose to share it.
      </Typography>
    </Stack>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <Paper sx={{ p: 3, flex: 1, minWidth: 0 }}>
      <Typography variant="overline" color="text.disabled"
                  sx={{ letterSpacing: "0.1em", fontSize: 10 }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: 28, fontWeight: 750, letterSpacing: "-0.03em", mt: 0.5 }}>
        {value}
      </Typography>
    </Paper>
  );
}

/**
 * The tile that refuses to lie.
 *
 * `null` value → words, not a number. And when there *is* a figure it never appears without its
 * coverage: a total over 40% of a collection is a different number from a total over all of it,
 * and showing them identically is how a partial valuation gets read as a complete one.
 */
function ValueTile({ value }: { value: DashboardData["value"] }) {
  return (
    <Paper sx={{ p: 3, flex: 1, minWidth: 0 }}>
      <Typography variant="overline" color="text.disabled"
                  sx={{ letterSpacing: "0.1em", fontSize: 10 }}>
        Estimated value
      </Typography>
      {value ? (
        <>
          <Typography sx={{ fontSize: 28, fontWeight: 750, letterSpacing: "-0.03em", mt: 0.5 }}>
            {formatMoney(value.total_cents, value.currency)}
          </Typography>
          <Typography variant="caption" color="text.disabled">
            {value.valued_items} of {value.total_items} valued · {value.confidence} confidence
          </Typography>
        </>
      ) : (
        <>
          <Typography sx={{ fontSize: 20, fontWeight: 600, mt: 0.5, color: "text.secondary" }}>
            Available in phase 2
          </Typography>
          <Typography variant="caption" color="text.disabled">
            Not a zero — a zero would be a claim.
          </Typography>
        </>
      )}
    </Paper>
  );
}

function RecentActivity({ recent }: { recent: DashboardData["recent"] }) {
  if (!recent.length) return null;
  return (
    <Box>
      <Typography variant="overline" color="text.disabled">Recent activity</Typography>
      <Stack sx={{ mt: 1, gap: 0.5 }}>
        {recent.map((row) => (
          <Stack key={row.id} direction="row" sx={{ gap: 2, alignItems: "baseline" }}>
            <Typography component={Link} to={`/cards/${row.card_id}`}
                        sx={{ fontSize: 14, color: "inherit" }}>
              {row.name}
            </Typography>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
              {row.set_code} {row.collector_number} · ×{row.quantity}
            </Typography>
            <Typography sx={{ fontSize: 12, color: "text.disabled", ml: "auto" }}>
              {row.updated_at.slice(0, 10)}
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Box>
  );
}
