import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteSealed, fetchSealed, openSealed } from "../api/backend";
import { formatMoney } from "../components/MoneyFigure";

/**
 * `/sealed` — story 025.
 *
 * Kept visibly separate from the collection, because it *is* separate: sealed product lives in its
 * own table and appears in no completion figure. A page that looked like `/collection` would imply
 * the two mix, and the whole point is that they never do.
 *
 * **Opening a box creates no singles**, and the page says so where somebody is about to click it.
 * That is not a limitation to apologise for: a box has an expected distribution and an actual pull,
 * they are never the same, and generated cards would be wrong every time in a way the collector has
 * to find and undo one row at a time.
 */
export function SealedPage() {
  const { getAccessToken } = useAuth();
  const client = useQueryClient();

  const sealed = useQuery({
    queryKey: ["sealed"],
    queryFn: () => fetchSealed(getAccessToken),
  });

  const open = useMutation({
    mutationFn: ({ id, quantity }: { id: string; quantity: number }) =>
      openSealed(id, quantity, getAccessToken),
    onSettled: () => client.invalidateQueries({ queryKey: ["sealed"] }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteSealed(id, getAccessToken),
    onSettled: () => client.invalidateQueries({ queryKey: ["sealed"] }),
  });

  if (sealed.isLoading) return <CircularProgress />;
  if (sealed.isError) return <Alert severity="error">{(sealed.error as Error).message}</Alert>;

  const data = sealed.data!;

  return (
    <Stack sx={{ gap: 3 }}>
      <Box>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>Sealed</Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
          Packs, boxes and decks. These are tracked separately from singles and never count towards
          set completion.
        </Typography>
      </Box>

      {data.total === 0 ? (
        <Stack sx={{ gap: 2, p: 6, alignItems: "center", textAlign: "center" }}>
          <Typography sx={{ fontSize: 18, fontWeight: 600 }}>No sealed product yet.</Typography>
          <Typography sx={{ fontSize: 14, color: "text.secondary", maxWidth: 420 }}>
            Boxes, packs and decks you have not opened — worth recording separately, because what
            they are worth and what is inside them are different questions.
          </Typography>
        </Stack>
      ) : (
        <>
          <Stack direction="row" sx={{ gap: 3 }}>
            <Figure label="Still sealed" value={data.sealed_count} />
            <Figure label="Opened" value={data.opened_count} />
          </Stack>

          <Stack sx={{ gap: 1 }}>
            {data.items.map((item) => (
              <Paper key={item.id} variant="outlined" sx={{ p: 2 }}>
                <Stack direction="row" sx={{ gap: 2, alignItems: "center", flexWrap: "wrap" }}>
                  <Box sx={{ flex: 1, minWidth: 200 }}>
                    <Typography sx={{ fontWeight: 600 }}>{item.name}</Typography>
                    <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
                      {item.kind.replace(/_/g, " ")}
                      {item.storage_location ? ` · ${item.storage_location}` : ""}
                      {item.acquired_unit_price_cents !== null && item.acquired_currency
                        ? ` · paid ${formatMoney(item.acquired_unit_price_cents,
                                                 item.acquired_currency)} each`
                        : ""}
                    </Typography>
                  </Box>

                  <Chip
                    size="small"
                    label={item.is_sealed ? "Sealed" : "Opened"}
                    color={item.is_sealed ? "primary" : "default"}
                    variant={item.is_sealed ? "filled" : "outlined"}
                  />
                  <Typography sx={{ fontWeight: 600, minWidth: 32 }}>×{item.quantity}</Typography>

                  {item.is_sealed ? (
                    <Button
                      size="small"
                      disabled={open.isPending}
                      onClick={() => open.mutate({ id: item.id, quantity: 1 })}
                    >
                      Mark one opened
                    </Button>
                  ) : null}
                  <Button size="small" color="error" onClick={() => remove.mutate(item.id)}>
                    Remove
                  </Button>
                </Stack>
              </Paper>
            ))}
          </Stack>

          {/* Stated where the button is, not buried in a help page. Someone about to open a box
              deserves to know what will and will not happen to their collection. */}
          <Alert severity="info">
            Marking a box opened records that it is opened. It does <strong>not</strong> add cards
            to your collection — the cards you actually pulled are never the expected distribution,
            so guessing would be wrong every time. Add what you pulled from the add page.
          </Alert>
        </>
      )}
    </Stack>
  );
}

function Figure({ label, value }: { label: string; value: number }) {
  return (
    <Box>
      <Typography sx={{ fontSize: 24, fontWeight: 700, lineHeight: 1 }}>{value}</Typography>
      <Typography sx={{ fontSize: 12, color: "text.secondary" }}>{label}</Typography>
    </Box>
  );
}
