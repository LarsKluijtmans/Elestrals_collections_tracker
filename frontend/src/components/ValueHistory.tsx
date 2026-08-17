import { Box, Stack, Typography, useTheme } from "@mui/material";
import type { HistoryPoint } from "../api/prices";
import { formatMoney } from "./MoneyFigure";

/**
 * Collection value over time — story 021.
 *
 * **The chart breaks where the data breaks.** A day with no value is a *gap*, not a zero and not a
 * line drawn between its neighbours. Interpolating invents a number, and a flat line at zero reads
 * as "this collection was worth nothing", which is a different and false claim from "we could not
 * value it".
 *
 * Counts are still drawn over the stretch where values are null, because they are real history:
 * "you owned 400 cards in March and 900 now" is a true answer that needs no pricing at all, and
 * throwing it away because the harvester had not started yet would lose months of it.
 *
 * Inline SVG rather than a charting dependency — one series, no axes, the same call `PriceHistory`
 * made. A library would be a larger commitment than the feature.
 */
export function ValueHistory({
  points, pricesStartOn,
}: { points: HistoryPoint[]; pricesStartOn: string | null }) {
  const theme = useTheme();

  if (points.length < 2) {
    return (
      <Typography sx={{ fontSize: 13, color: "text.disabled" }}>
        Not enough history yet — the chart appears once there are a few days of it.
      </Typography>
    );
  }

  const width = 640;
  const height = 160;
  const valued = points.filter((p) => p.total_value_cents !== null);
  const max = Math.max(...valued.map((p) => p.total_value_cents ?? 0), 1);
  const maxCount = Math.max(...points.map((p) => p.item_count), 1);

  const x = (index: number) => (index / (points.length - 1)) * width;
  const y = (cents: number) => height - (cents / max) * (height - 8) - 4;
  const yCount = (count: number) => height - (count / maxCount) * (height - 8) - 4;

  // Segments, not one path. A `null` ends the current run and the next value starts a new one —
  // which is what makes the gap visible instead of being bridged by a straight line through
  // days nobody has a number for.
  const segments: string[] = [];
  let current: string[] = [];
  points.forEach((point, index) => {
    if (point.total_value_cents === null) {
      if (current.length > 1) segments.push(current.join(" "));
      current = [];
      return;
    }
    current.push(`${current.length ? "L" : "M"}${x(index).toFixed(1)},${y(point.total_value_cents).toFixed(1)}`);
  });
  if (current.length > 1) segments.push(current.join(" "));

  const countPath = points
    .map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${yCount(p.item_count).toFixed(1)}`)
    .join(" ");

  const latest = [...points].reverse().find((p) => p.total_value_cents !== null);

  return (
    <Stack sx={{ gap: 1 }}>
      <Box
        component="svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={
          latest
            ? `Collection value over ${points.length} days, most recently ` +
              `${formatMoney(latest.total_value_cents!, latest.currency)}`
            : `Card count over ${points.length} days. No values available yet.`
        }
        sx={{ width: "100%", height: "auto", overflow: "visible" }}
      >
        {/* Counts underneath, always drawn: real history that needs no prices. */}
        <path
          d={countPath}
          fill="none"
          stroke={theme.palette.text.disabled}
          strokeWidth={1}
          strokeDasharray="3 3"
        />
        {segments.map((d, index) => (
          <path
            key={index}
            d={d}
            fill="none"
            stroke={theme.palette.primary.main}
            strokeWidth={2}
            strokeLinecap="round"
          />
        ))}
      </Box>

      <Stack direction="row" sx={{ gap: 2, flexWrap: "wrap" }}>
        <Legend colour={theme.palette.primary.main} label="Value" />
        <Legend colour={theme.palette.text.disabled} label="Cards held" dashed />
      </Stack>

      {pricesStartOn && points[0] && points[0].day < pricesStartOn ? (
        // Said plainly rather than left as a mysterious gap at the left-hand edge.
        <Typography sx={{ fontSize: 12, color: "text.disabled" }}>
          Values start on {pricesStartOn} — that is when price data begins. The card count before
          then is real; there was simply nothing to value it with.
        </Typography>
      ) : null}
    </Stack>
  );
}

function Legend({
  colour, label, dashed,
}: { colour: string; label: string; dashed?: boolean }) {
  return (
    <Stack direction="row" sx={{ gap: 0.5, alignItems: "center" }}>
      <Box sx={{
        width: 16, height: 0, borderTop: dashed ? "1px dashed" : "2px solid", borderColor: colour,
      }} />
      <Typography sx={{ fontSize: 11, color: "text.secondary" }}>{label}</Typography>
    </Stack>
  );
}
