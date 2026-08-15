// The landing surface. Real stat tiles and completion rings arrive in bolt 006; the value
// tile is deliberately absent until phase 2 — a zero is a claim, and it would be false.
import { Box, Paper, Stack, Typography } from "@mui/material";
import { ProfileCard } from "../components/ProfileCard";

export function DashboardPage() {
  return (
    <Stack spacing={6}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 750, letterSpacing: "-0.025em" }}>
          Your collection
        </Typography>
        <Typography color="text.secondary" sx={{ mt: 1, maxWidth: "60ch" }}>
          Signed in, themed from platform branding, and logging every request. The catalog
          arrives in bolt 002.
        </Typography>
      </Box>

      <Stack direction={{ xs: "column", md: "row" }} spacing={4}>
        <Tile label="Items" value="—" note="after bolt 004" />
        <Tile label="Printings" value="—" note="after bolt 002" />
        <Tile label="Sets started" value="—" note="after bolt 004" />
        <Tile label="Est. value" value="Phase 2" note="not a zero — a zero is a claim" />
      </Stack>

      <ProfileCard />
    </Stack>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <Paper sx={{ p: 4, flex: 1, minWidth: 0 }}>
      <Typography
        variant="overline"
        color="text.disabled"
        sx={{ letterSpacing: "0.1em", fontSize: 10 }}
      >
        {label}
      </Typography>
      <Typography sx={{ fontSize: 24, fontWeight: 750, letterSpacing: "-0.03em", mt: 1 }}>
        {value}
      </Typography>
      <Typography variant="caption" color="text.disabled">
        {note}
      </Typography>
    </Paper>
  );
}
