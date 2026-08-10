// /cards/:cardId — one card with every printing. Public: works signed out.
import { Alert, Box, Divider, Skeleton, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { Link as RouterLink, useParams } from "react-router-dom";
import { fetchCard } from "../api/backend";
import { ElementChip } from "../components/ElementChip";
import { PrintingTable } from "../components/PrintingTable";

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

      {data.artist && (
        <Typography sx={{ fontSize: 12, color: "text.disabled" }}>Art by {data.artist}</Typography>
      )}
    </Stack>
  );
}
