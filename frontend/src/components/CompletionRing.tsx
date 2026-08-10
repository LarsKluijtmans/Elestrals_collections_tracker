// Set completion ring.
//
// `completion === null` renders the track alone. That is the signed-out state *and* the
// pre-bolt-004 state, and it is why `/sets` can stay anonymous and cacheable: completion is
// per-user, so it is fetched separately and merged in, never baked into the set response.
import { Box, Tooltip } from "@mui/material";
import { useTheme } from "@mui/material/styles";

export function CompletionRing({
  completion,
  size = 44,
  label,
}: {
  /** 0–1, or null when unknown (signed out, or not yet loaded). */
  completion: number | null;
  size?: number;
  label?: string;
}) {
  const theme = useTheme();
  const stroke = 4;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = completion === null ? 0 : Math.max(0, Math.min(1, completion));
  const offset = circumference * (1 - clamped);

  const text = completion === null ? "—" : `${Math.round(clamped * 100)}%`;
  const title = label ?? (completion === null ? "Sign in to see completion" : `${text} complete`);

  return (
    <Tooltip title={title}>
      <Box
        sx={{ position: "relative", width: size, height: size, flexShrink: 0 }}
        role="img"
        aria-label={title}
      >
        <Box component="svg" sx={{ width: size, height: size, transform: "rotate(-90deg)" }}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={theme.palette.divider}
            strokeWidth={stroke}
          />
          {completion !== null && (
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={theme.palette.primary.main}
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
            />
          )}
        </Box>
        <Box
          sx={{
            position: "absolute",
            inset: 0,
            display: "grid",
            placeItems: "center",
            fontSize: 11,
            fontWeight: 600,
            color: completion === null ? "text.disabled" : "text.primary",
          }}
        >
          {text}
        </Box>
      </Box>
    </Tooltip>
  );
}
