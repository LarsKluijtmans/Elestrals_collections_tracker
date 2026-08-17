import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { deleteWish, fetchWishlist } from "../api/backend";
import { ElementChip } from "../components/ElementChip";
import { formatMoney } from "../components/MoneyFigure";
import { RarityBadge } from "../components/RarityBadge";

/**
 * `/wishlist` — story 026.
 *
 * The design decision worth defending is what this page does when you acquire something you wished
 * for: **it offers to clear the wish, and does nothing until you say so.**
 *
 * Auto-clearing is the obvious behaviour and it is wrong. A collector may want a playset, or a
 * better condition, or a first edition of something they own unlimited. Deleting their stated
 * intent because a row appeared elsewhere destroys information they cannot recover and never
 * agreed to lose — so the row is flagged, prominently, and the button is theirs to press.
 */
export function WishlistPage() {
  const { getAccessToken } = useAuth();
  const client = useQueryClient();

  const wishlist = useQuery({
    queryKey: ["wishlist"],
    queryFn: () => fetchWishlist(getAccessToken),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteWish(id, getAccessToken),
    onSettled: () => client.invalidateQueries({ queryKey: ["wishlist"] }),
  });

  if (wishlist.isLoading) return <CircularProgress />;
  if (wishlist.isError) {
    return <Alert severity="error">{(wishlist.error as Error).message}</Alert>;
  }

  const data = wishlist.data!;

  return (
    <Stack sx={{ gap: 3 }}>
      <Box>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>Wishlist</Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
          Cards you are looking for, with an optional ceiling on what you will pay.
        </Typography>
      </Box>

      {data.acquired_count > 0 ? (
        <Alert severity="success">
          {data.acquired_count === 1
            ? "One card on this list is now in your collection."
            : `${data.acquired_count} cards on this list are now in your collection.`}{" "}
          They are still here — clear them yourself if you are done wanting them. You might want a
          second copy, or a better one.
        </Alert>
      ) : null}

      {data.total === 0 ? (
        <Stack sx={{ gap: 2, p: 6, alignItems: "center", textAlign: "center" }}>
          <Typography sx={{ fontSize: 18, fontWeight: 600 }}>Nothing on the list yet.</Typography>
          <Typography sx={{ fontSize: 14, color: "text.secondary", maxWidth: 420 }}>
            Add a card from its detail page and it will show up here, with what you are willing to
            pay for it.
          </Typography>
          <Button component={Link} to="/sets" variant="outlined">Browse sets</Button>
        </Stack>
      ) : (
        <Stack sx={{ gap: 1 }}>
          {data.items.map((entry) => (
            <Paper key={entry.id} variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" sx={{ gap: 2, alignItems: "center", flexWrap: "wrap" }}>
                <Box sx={{ flex: 1, minWidth: 200 }}>
                  <Typography
                    component={Link}
                    to={`/cards/${entry.card_id}`}
                    sx={{ fontWeight: 600, color: "inherit", display: "block" }}
                  >
                    {entry.name}
                  </Typography>
                  <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
                    {entry.set_code} {entry.collector_number} · {entry.finish.replace(/_/g, " ")}
                  </Typography>
                </Box>

                <ElementChip element={entry.element} size="xs" />
                <RarityBadge rarity={entry.rarity} element={entry.element} />

                {entry.priority !== "normal" ? (
                  <Chip size="small" variant="outlined" label={entry.priority} />
                ) : null}

                <Typography sx={{ fontSize: 13, minWidth: 40 }}>
                  ×{entry.desired_quantity}
                </Typography>

                <Typography sx={{ fontSize: 13, minWidth: 90, color: "text.secondary" }}>
                  {/* Only ever shown as money. The schema refuses an amount without a currency,
                      so there is no half-price state to render. */}
                  {entry.max_price_cents !== null && entry.max_price_currency
                    ? `up to ${formatMoney(entry.max_price_cents, entry.max_price_currency)}`
                    : "—"}
                </Typography>

                {entry.owned ? (
                  <Chip size="small" color="success" label="You own this" />
                ) : null}

                <Button size="small" onClick={() => remove.mutate(entry.id)}>
                  {entry.owned ? "Clear wish" : "Remove"}
                </Button>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}
    </Stack>
  );
}
