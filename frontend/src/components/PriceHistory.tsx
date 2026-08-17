import {
  Alert, Box, Chip, CircularProgress, Stack, ToggleButton, ToggleButtonGroup, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { pricesApi, type PricePoint } from "../api/prices";
import { MoneyFigure, formatMoney } from "./MoneyFigure";

const RANGES = [
  { key: "30d", label: "30 days" },
  { key: "90d", label: "90 days" },
  { key: "365d", label: "1 year" },
  { key: "all", label: "All" },
];

/**
 * The price tab's contents for one printing.
 *
 * Two presentation rules, both from the requirements and both easy to break by accident:
 *
 * * **An empty state is an empty state.** A printing with no data shows "no sales seen", never a
 *   flat line at zero — a chart at zero reads as "this card is worthless", which is a different
 *   and false claim from "we have not seen one sell".
 * * **Every series states its observation count.** A median from two sales and one from two
 *   hundred are drawn identically and mean very different things.
 *
 * The sparkline is inline SVG rather than a charting dependency: it draws one series with no
 * axes, and adding a library for that would be a larger commitment than the feature.
 */
export function PriceHistoryPanel({ printingId }: { printingId: string }) {
  const [range, setRange] = useState("90d");
  const [saleType, setSaleType] = useState<"sold" | "listed">("sold");

  const history = useQuery({
    queryKey: ["prices", printingId, range, saleType],
    queryFn: () => pricesApi.history(printingId, { range, sale_type: saleType }),
  });

  if (history.isLoading) return <CircularProgress />;
  if (history.isError) {
    return (
      <Alert severity="warning">
        Prices are unavailable right now. The rest of the card is unaffected.
      </Alert>
    );
  }

  const data = history.data!;
  const latest = data.points.at(-1);

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2} sx={{ alignItems: "center", flexWrap: "wrap" }}>
        <ToggleButtonGroup
          size="small" exclusive value={range}
          onChange={(_, value) => value && setRange(value)}
        >
          {RANGES.map((option) => (
            <ToggleButton key={option.key} value={option.key}>{option.label}</ToggleButton>
          ))}
        </ToggleButtonGroup>

        <ToggleButtonGroup
          size="small" exclusive value={saleType}
          onChange={(_, value) => value && setSaleType(value)}
        >
          <ToggleButton value="sold">Sold</ToggleButton>
          {/* Labelled as asking prices, and `low` confidence by definition. `sold` and `listed`
              are never blended into one series. */}
          <ToggleButton value="listed">Asking</ToggleButton>
        </ToggleButtonGroup>

        {data.is_stale && !data.is_empty ? (
          <Chip
            size="small" color="warning" variant="outlined"
            label={`Last updated ${data.priced_as_of ? new Date(data.priced_as_of).toLocaleDateString() : "a while ago"}`}
          />
        ) : null}
      </Stack>

      {data.is_empty ? (
        <Alert severity="info">
          No {saleType === "sold" ? "sales" : "listings"} seen for this printing yet.
        </Alert>
      ) : (
        <>
          <MoneyFigure
            cents={latest?.median_cents ?? null}
            currency={latest?.currency ?? "EUR"}
            confidence={latest?.confidence ?? "low"}
            observationCount={latest?.observation_count ?? 0}
            variant="h4"
            label="Median"
          />
          <Sparkline points={data.points} />
          <Stack direction="row" spacing={3} sx={{ flexWrap: "wrap" }}>
            <Stat label="Low" value={formatMoney(min(data.points), latest?.currency ?? "EUR")} />
            <Stat label="High" value={formatMoney(max(data.points), latest?.currency ?? "EUR")} />
            <Stat
              label="Observations"
              value={String(data.points.reduce((sum, p) => sum + p.observation_count, 0))}
            />
            <Stat label="Days with data" value={String(data.points.length)} />
          </Stack>
        </>
      )}
    </Stack>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="overline" color="text.secondary">{label}</Typography>
      <Typography variant="body1">{value}</Typography>
    </Box>
  );
}

function Sparkline({ points }: { points: PricePoint[] }) {
  if (points.length < 2) {
    return (
      <Typography variant="body2" color="text.secondary">
        One data point — not enough to draw a trend, and drawing one anyway would imply a
        movement nobody observed.
      </Typography>
    );
  }

  const width = 600;
  const height = 120;
  const lowest = min(points);
  const highest = max(points);
  const span = highest - lowest || 1;

  const path = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * width;
      const y = height - ((point.median_cents - lowest) / span) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <Box
      component="svg"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Median price over ${points.length} days`}
      sx={{ width: "100%", maxWidth: width, height: "auto", overflow: "visible" }}
    >
      <path d={path} fill="none" stroke="currentColor" strokeWidth={2} />
      {points.map((point, index) => (
        <circle
          key={point.day}
          cx={(index / (points.length - 1)) * width}
          cy={height - ((point.median_cents - lowest) / span) * height}
          // Thin days are drawn smaller. The count is in the tooltip either way, but a point
          // built from one sale should not look as solid as one built from twenty.
          r={point.observation_count >= 5 ? 4 : 2}
          fill="currentColor"
        >
          <title>
            {point.day}: {formatMoney(point.median_cents, point.currency)} ·{" "}
            {point.observation_count} observation(s) · {point.confidence}
          </title>
        </circle>
      ))}
    </Box>
  );
}

const min = (points: PricePoint[]) => Math.min(...points.map((p) => p.low_cents));
const max = (points: PricePoint[]) => Math.max(...points.map((p) => p.high_cents));
