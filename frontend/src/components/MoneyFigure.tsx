import { Stack, Tooltip, Typography } from "@mui/material";
import { ConfidencePill, type Confidence } from "./ConfidencePill";

type Props = {
  cents: number | null;
  currency: string;
  /**
   * **Required, not optional.** Standards §8: no monetary figure renders without its
   * confidence. Making this a required prop is how that rule is kept true — a figure without
   * one fails to compile rather than shipping and being noticed later, or never.
   */
  confidence: Confidence;
  /** Also required. A median from two sales and a median from two hundred are the same number
   *  and mean very different things, and only this tells them apart. */
  observationCount: number;
  label?: string;
  variant?: "body1" | "h5" | "h4";
};

/**
 * A price, with the two things that make it readable rather than merely legible.
 *
 * A null amount renders as an honest empty state — never as a zero. "€0.00" reads as "this is
 * worthless", which is a different and false claim from "we have not seen one sell".
 */
export function MoneyFigure({
  cents,
  currency,
  confidence,
  observationCount,
  label,
  variant = "body1",
}: Props) {
  if (cents === null) {
    return (
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant={variant} color="text.secondary">
          No sales seen
        </Typography>
        <ConfidencePill confidence="low" observationCount={0} />
      </Stack>
    );
  }

  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
      {label ? (
        <Typography variant="body2" color="text.secondary">
          {label}
        </Typography>
      ) : null}
      <Tooltip title={`${observationCount} observation(s)`}>
        <Typography variant={variant} sx={{ fontWeight: 600 }}>
          {formatMoney(cents, currency)}
        </Typography>
      </Tooltip>
      <ConfidencePill confidence={confidence} observationCount={observationCount} />
    </Stack>
  );
}

export function formatMoney(cents: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(cents / 100);
}
