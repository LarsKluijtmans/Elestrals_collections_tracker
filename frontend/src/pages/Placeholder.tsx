// Placeholder pages for phase-1 routes whose real implementations land in later bolts.
//
// Each one names the bolt that will replace it. That is deliberate: an honest "not built
// yet, arriving in bolt 006" is more useful than a convincing empty state that leaves you
// wondering whether the feature is broken or absent.
import { Box, Chip, Paper, Stack, Typography } from "@mui/material";

export function Placeholder({
  title, bolt, children,
}: {
  title: string;
  bolt: string;
  children?: React.ReactNode;
}) {
  return (
    <Stack spacing={6}>
      <Box>
        <Stack direction="row" spacing={3} sx={{ alignItems: "center" }}>
          <Typography variant="h4" sx={{ fontWeight: 750, letterSpacing: "-0.025em" }}>
            {title}
          </Typography>
          <Chip size="small" variant="outlined" label={bolt} sx={{ fontFamily: "monospace" }} />
        </Stack>
        {children && (
          <Typography color="text.secondary" sx={{ mt: 2, maxWidth: "60ch" }}>
            {children}
          </Typography>
        )}
      </Box>
      <Paper sx={{ p: 8, textAlign: "center" }}>
        <Typography color="text.disabled">
          Not built yet. The foundation this sits on — auth, theming, logging, the database —
          is in place.
        </Typography>
      </Paper>
    </Stack>
  );
}

export const CollectionPage = () => (
  <Placeholder title="Collection" bolt="bolt 006">
    The virtualized table, filter rail, saved views and bulk actions. Needs the catalog
    (bolt 002) and the inventory write model (bolt 004) beneath it first.
  </Placeholder>
);

// AddCardsPage is no longer a placeholder — bolt 005 built it. See pages/collection/AddCards.tsx.

export const SetsPage = () => (
  <Placeholder title="Sets" bolt="bolt 003">
    The set gallery with completion rings, and the per-set checklist.
  </Placeholder>
);

export const SealedPage = () => (
  <Placeholder title="Sealed" bolt="bolt 007">
    Packs, boxes and decks — tracked separately, and never counted in singles maths.
  </Placeholder>
);

export const WishlistPage = () => (
  <Placeholder title="Wishlist" bolt="bolt 007">
    Wanted printings with a desired quantity and a maximum price. Becomes the seed for
    phase-2 price alerts.
  </Placeholder>
);

export const ImportExportPage = () => (
  <Placeholder title="Import / export" bolt="bolt 008">
    CSV in and out, with a dry-run diff you confirm before anything is written.
  </Placeholder>
);

export const NotFoundPage = () => (
  <Placeholder title="Page not found" bolt="404">
    That route does not exist. Navigation is still available on the left.
  </Placeholder>
);
