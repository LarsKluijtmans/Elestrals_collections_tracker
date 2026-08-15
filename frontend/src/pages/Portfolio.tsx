import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Chip, CircularProgress, LinearProgress, Paper, Stack, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { pricesApi } from "../api/prices";
import { ConfidencePill } from "../components/ConfidencePill";
import { formatMoney } from "../components/MoneyFigure";

/**
 * `/portfolio` — what this collection is worth, and how much of it that covers.
 *
 * The coverage line is not a footnote. An item with no price is **excluded and counted, never
 * treated as zero**: a zero for an unpriced holding produces a total that is confidently wrong
 * and silently low, and nobody reading the number can tell unless the page says so.
 */
export function PortfolioPage() {
  const { getAccessToken } = useAuth();
  const portfolio = useQuery({
    queryKey: ["portfolio"],
    queryFn: () => pricesApi.portfolio(getAccessToken),
  });

  if (portfolio.isLoading) return <CircularProgress />;
  if (portfolio.isError) {
    return (
      <Alert severity="warning">
        Valuation is unavailable right now. Your collection itself is unaffected.
      </Alert>
    );
  }

  const data = portfolio.data!;
  const nothingValued = data.valued_items === 0;

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Portfolio</Typography>

      <Paper sx={{ p: 3 }}>
        {nothingValued ? (
          // Not "€0.00". A zero total for a collection nothing has been seen selling is a
          // different and false claim from "we could not value any of it".
          <Alert severity="info">
            {data.unvalued_items === 0
              ? "Nothing in your collection yet."
              : `None of your ${data.unvalued_items} item(s) could be valued yet — no sales have been seen for them.`}
          </Alert>
        ) : (
          <>
            <Stack direction="row" spacing={2} sx={{ alignItems: "baseline" }}>
              <Typography variant="h3">
                {formatMoney(data.total_cents, data.currency)}
              </Typography>
              <ConfidencePill
                confidence={data.confidence}
                observationCount={data.valued_items}
              />
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {data.valued_items} of {data.valued_items + data.unvalued_items} items valued
            </Typography>
            <LinearProgress
              variant="determinate"
              value={data.coverage * 100}
              sx={{ mt: 1, maxWidth: 420 }}
            />
          </>
        )}

        {data.priced_as_of ? (
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 2 }}>
            Priced from data published {new Date(data.priced_as_of).toLocaleString()}
          </Typography>
        ) : null}
      </Paper>

      {data.unvalued_items > 0 ? (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6">What could not be valued</Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            These are excluded from the total rather than counted as zero.
          </Typography>
          <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", mt: 1 }}>
            {Object.entries(data.unvalued_reasons).map(([reason, count]) => (
              <Chip key={reason} label={`${count} × ${REASONS[reason] ?? reason}`} />
            ))}
          </Stack>
        </Paper>
      ) : null}

      <Alert severity="info" variant="outlined">
        We report observed sales — we do not set or predict prices. Every figure shows how many
        observations it is built from and how confident we are in it. This is not investment
        advice.
      </Alert>
    </Stack>
  );
}

const REASONS: Record<string, string> = {
  no_data: "no sales seen yet",
  // The matcher refuses graded slabs on purpose: a PSA 10 and a raw copy are two markets, and
  // there is nowhere in the schema to record a grade. So there is no graded price to use.
  graded: "graded — we do not collect graded prices",
  no_rate: "no exchange rate for that day",
};
