import { Chip, Tooltip } from "@mui/material";

export type Confidence = "low" | "medium" | "high";

type Props = {
  confidence: Confidence;
  observationCount: number;
};

/**
 * The visible statement of how much a figure is worth trusting.
 *
 * The rule it renders, from the requirements and computed once in the harvester's rollup:
 *
 *     high    ≥ 5 sold observations from ≥ 2 sources in the window
 *     medium  ≥ 2 sold observations
 *     low     anything else, INCLUDING anything derived from asking prices
 *
 * The last clause is the one worth explaining in a tooltip rather than leaving to be inferred.
 * Under ADR-004 more of this data is thin, single-source or asking-price-derived than it would
 * have been under a licensed feed, so `low` is common and needs to mean something specific to
 * the person reading it.
 *
 * Colours are semantic tokens, not the element palette — a price's confidence has nothing to do
 * with a card's element, and reusing that palette here would imply a relationship.
 */
export function ConfidencePill({ confidence, observationCount }: Props) {
  const { color, tip } = DESCRIPTIONS[confidence];
  return (
    <Tooltip title={`${tip} (${observationCount} observation${observationCount === 1 ? "" : "s"})`}>
      <Chip size="small" variant="outlined" color={color} label={confidence} />
    </Tooltip>
  );
}

const DESCRIPTIONS: Record<
  Confidence,
  { color: "success" | "warning" | "default"; tip: string }
> = {
  high: {
    color: "success",
    tip: "Five or more sales, seen by at least two independent sources",
  },
  medium: {
    color: "warning",
    tip: "At least two sales, but from a single source or a thin window",
  },
  low: {
    color: "default",
    tip: "One sale, or derived from asking prices rather than completed sales",
  },
};
