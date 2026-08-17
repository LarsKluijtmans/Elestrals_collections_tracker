// /cards/:cardId — one card with every printing. Public: works signed out.
import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, Divider, MenuItem, Select, Skeleton, Stack, Tooltip, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { ApiError, addWish, fetchCard, type PrintingView } from "../api/backend";
import { ElementChip } from "../components/ElementChip";
import { PriceHistoryPanel } from "../components/PriceHistory";
import { PrintingTable } from "../components/PrintingTable";

/**
 * Add a printing to the wishlist — story 026.
 *
 * Signed-out visitors do not see it: this page is public and a wish is per-user, so offering the
 * button and then bouncing them to a login portal would be a worse first impression than not
 * offering it.
 *
 * A duplicate is a `409`, and it is reported as "already on your list" rather than as an error.
 * From the collector's point of view nothing went wrong — the card is on the list, which is what
 * they wanted.
 */
function WishButton({ printings }: { printings: PrintingView[] }) {
  const { isAuthenticated, getAccessToken } = useAuth();
  const client = useQueryClient();
  const [choice, setChoice] = useState<string>(printings[0]?.printing_id ?? "");

  const wish = useMutation({
    mutationFn: () => addWish({ printing_id: choice }, getAccessToken),
    onSettled: () => client.invalidateQueries({ queryKey: ["wishlist"] }),
  });

  if (!isAuthenticated || !printings.length) return null;

  const already =
    wish.isError && (wish.error as ApiError)?.code === "already_wished";

  return (
    <Stack direction="row" sx={{ gap: 1, ml: "auto", alignItems: "center" }}>
      {printings.length > 1 ? (
        <Select
          size="small"
          value={choice}
          onChange={(event) => setChoice(event.target.value)}
          sx={{ fontSize: 12 }}
          inputProps={{ "aria-label": "Which printing to wish for" }}
        >
          {printings.map((printing) => (
            <MenuItem key={printing.printing_id} value={printing.printing_id}>
              {printing.rarity} · {printing.finish}
            </MenuItem>
          ))}
        </Select>
      ) : null}

      <Tooltip title={already ? "Already on your wishlist" : "Add to wishlist"}>
        <span>
          <Button
            size="small"
            variant="outlined"
            disabled={wish.isPending || wish.isSuccess || already}
            onClick={() => wish.mutate()}
          >
            {wish.isSuccess ? "On your wishlist" : already ? "Already wished" : "Wishlist"}
          </Button>
        </span>
      </Tooltip>
    </Stack>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Box>
      <Typography sx={{ fontSize: 11, color: "text.disabled", textTransform: "uppercase" }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: 16, fontWeight: 650 }}>{value}</Typography>
    </Box>
  );
}

export function CardDetailPage() {
  const { id = "" } = useParams();
  // Prices attach to a PRINTING, not to a card: a foil first edition and a plain unlimited are
  // two different markets, and averaging them would be the same mistake the matcher refuses to
  // make. So the price panel needs a printing chosen, and defaults to the first.
  const [pricedPrinting, setPricedPrinting] = useState<string | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ["card", id],
    queryFn: () => fetchCard(id),
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <Skeleton variant="rounded" height={360} />;
  if (error || !data) return <Alert severity="error">Could not load this card.</Alert>;

  const art = data.printings.find((p) => p.image_url);

  return (
    <Stack sx={{ gap: 3, maxWidth: 900 }}>
      <Box>
        <Typography
          component={RouterLink}
          to={`/sets/${data.set_code}`}
          sx={{ fontSize: 12, color: "text.secondary", textDecoration: "none" }}
        >
          {data.set_name} ({data.set_code}) · {data.collector_number}
        </Typography>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650, mt: 0.5 }}>
          {data.name}
        </Typography>
        <Stack direction="row" sx={{ gap: 1, mt: 1, alignItems: "center" }}>
          <ElementChip element={data.element} />
          <Typography sx={{ fontSize: 12, color: "text.secondary", textTransform: "capitalize" }}>
            {data.card_type}
            {data.rune_type ? ` · ${data.rune_type}` : ""}
            {data.subtype ? ` · ${data.subtype}` : ""}
          </Typography>
          {/* Wishing is per *printing*, not per card — a foil first edition and a plain unlimited
              are different things to want, and different things to price-alert on later. */}
          <WishButton printings={data.printings} />
        </Stack>
      </Box>

      {art?.image_url && (
        <Box
          component="img"
          src={art.image_url}
          // Central alt text: "{name} — {set} {rarity}". ux-guide §9, binding.
          alt={art.alt_text}
          sx={{ maxWidth: 320, borderRadius: 2, alignSelf: "flex-start" }}
        />
      )}

      {(data.attack !== null || data.defence !== null || data.spirit_cost) && (
        <Stack direction="row" sx={{ gap: 4 }}>
          {data.attack !== null && <Stat label="Attack" value={data.attack} />}
          {data.defence !== null && <Stat label="Defence" value={data.defence} />}
          {data.spirit_cost && (
            <Stat
              label="Spirit cost"
              value={Object.entries(data.spirit_cost)
                .map(([element, count]) => `${count} ${element}`)
                .join(" · ")}
            />
          )}
        </Stack>
      )}

      {data.rules_text && (
        <Box>
          <Typography sx={{ fontSize: 14, whiteSpace: "pre-wrap" }}>{data.rules_text}</Typography>
        </Box>
      )}

      {data.flavour_text && (
        <Typography sx={{ fontSize: 13, fontStyle: "italic", color: "text.secondary" }}>
          {data.flavour_text}
        </Typography>
      )}

      <Divider />

      <Box>
        <Typography sx={{ fontSize: 20, fontWeight: 650, mb: 1.5 }}>
          Printings ({data.printings.length})
        </Typography>
        <PrintingTable printings={data.printings} element={data.element} />
      </Box>

      <Divider />

      <Box>
        <Stack direction="row" sx={{ gap: 2, alignItems: "center", mb: 1.5 }}>
          <Typography sx={{ fontSize: 20, fontWeight: 650 }}>Prices</Typography>
          <Select
            size="small"
            value={pricedPrinting ?? data.printings[0]?.printing_id ?? ""}
            onChange={(event) => setPricedPrinting(String(event.target.value))}
          >
            {data.printings.map((printing) => (
              <MenuItem key={printing.printing_id} value={printing.printing_id}>
                {printing.rarity} · {printing.finish} · {printing.edition}
              </MenuItem>
            ))}
          </Select>
        </Stack>
        {data.printings.length > 0 ? (
          <PriceHistoryPanel
            printingId={pricedPrinting ?? data.printings[0].printing_id}
          />
        ) : (
          <Typography sx={{ color: "text.secondary" }}>
            No printings to price yet.
          </Typography>
        )}
      </Box>

      {data.artist && (
        <Typography sx={{ fontSize: 12, color: "text.disabled" }}>Art by {data.artist}</Typography>
      )}
    </Stack>
  );
}
