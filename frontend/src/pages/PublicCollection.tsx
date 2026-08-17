import { Alert, Box, Skeleton, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link as RouterLink, useParams, useSearchParams } from "react-router-dom";
import { fetchPublicCollection, fetchSharedCollection } from "../api/backend";
import { ElementChip } from "../components/ElementChip";
import { RarityBadge } from "../components/RarityBadge";

/**
 * `/u/:handle` and the token-shared variant — story 033.
 *
 * **No session, and no private data.** The API builds this from a whitelist model that never had
 * cost basis, acquisition price, storage location or notes, so nothing here can leak them however
 * this component is written. That is the point of a whitelist over a filter: the safety is in the
 * shape of the data, not in the discipline of the page rendering it.
 *
 * A private or unknown handle returns 404 and this renders the same "not found" for both —
 * distinguishing them would tell a stranger which handles exist.
 */
export function PublicCollectionPage() {
  const { handle = "" } = useParams();
  const [params] = useSearchParams();
  const token = params.get("token");

  const collection = useQuery({
    queryKey: ["public", handle, token],
    queryFn: () => (token ? fetchSharedCollection(token) : fetchPublicCollection(handle)),
    staleTime: 60_000,
  });

  // A link-shared collection must not end up in a search index — the whole point of an
  // unguessable URL is that it is only reachable by people the owner sent it to.
  useEffect(() => {
    if (!collection.data?.unlisted) return;
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex, nofollow";
    document.head.appendChild(meta);
    return () => {
      document.head.removeChild(meta);
    };
  }, [collection.data?.unlisted]);

  if (collection.isLoading) return <Skeleton variant="rounded" height={320} />;

  if (!collection.data) {
    return (
      <Stack sx={{ gap: 2, p: 6, alignItems: "center", textAlign: "center" }}>
        <Typography sx={{ fontSize: 18, fontWeight: 600 }}>Nothing here.</Typography>
        <Typography sx={{ fontSize: 14, color: "text.secondary", maxWidth: 420 }}>
          This collection does not exist, or its owner has not made it public.
        </Typography>
      </Stack>
    );
  }

  const data = collection.data;

  return (
    <Stack sx={{ gap: 3 }}>
      <Box>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>
          {data.handle ? `${data.handle}’s collection` : "A shared collection"}
        </Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
          {data.total_items.toLocaleString()} cards across{" "}
          {data.distinct_printings.toLocaleString()} printings
        </Typography>
      </Box>

      {data.unlisted ? (
        <Alert severity="info">
          You are viewing this through a private link. It is not listed anywhere and search engines
          are asked not to index it — but anyone with the link can see it.
        </Alert>
      ) : null}

      {data.holdings.length === 0 ? (
        <Typography sx={{ color: "text.disabled" }}>This collection is empty.</Typography>
      ) : (
        <Stack sx={{ gap: 1 }}>
          {data.holdings.map((holding) => (
            <Box
              key={`${holding.printing_id}-${holding.condition}`}
              component={RouterLink}
              to={`/cards/${holding.card_id}`}
              sx={{
                display: "flex", alignItems: "center", gap: 1.5,
                px: 2, py: 1.25, borderRadius: 1.5, textDecoration: "none",
                color: "inherit", border: 1, borderColor: "divider",
                "&:hover": { bgcolor: "action.hover" },
              }}
            >
              <Typography sx={{ fontSize: 12, color: "text.disabled", minWidth: 90 }}>
                {holding.set_code} {holding.collector_number}
              </Typography>
              <Typography sx={{ fontSize: 14, fontWeight: 600, flexGrow: 1 }} noWrap>
                {holding.name}
              </Typography>
              <ElementChip element={holding.element} size="xs" />
              <RarityBadge rarity={holding.rarity} element={holding.element} />
              <Typography sx={{ fontSize: 12, color: "text.secondary", minWidth: 80 }}>
                {holding.condition.replace(/_/g, " ")}
              </Typography>
              <Typography sx={{ fontSize: 13, fontWeight: 600, minWidth: 32 }}>
                ×{holding.quantity}
              </Typography>
            </Box>
          ))}
        </Stack>
      )}

      <Typography sx={{ fontSize: 12, color: "text.disabled" }}>
        {/* Stated, because a viewer should be able to tell what they are and are not seeing. */}
        Shared collections show cards, conditions and quantities. What anything cost, where it is
        kept and any private notes are never included.
      </Typography>
    </Stack>
  );
}
