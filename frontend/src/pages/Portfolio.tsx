import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Chip, CircularProgress, LinearProgress, Paper, Stack, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { pricesApi } from "../api/prices";
import { ConfidencePill } from "../components/ConfidencePill";
import { formatMoney } from "../components/MoneyFigure";
import { ValueHistory } from "../components/ValueHistory";

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

      <HistoryPanel />

      <Alert severity="info" variant="outlined">
        We report observed sales — we do not set or predict prices. Every figure shows how many
        observations it is built from and how confident we are in it. This is not investment
        advice.
      </Alert>
    </Stack>
  );
}

/**
 * Value over time, P/L and what is carrying the collection — story 021.
 *
 * Its own query, deliberately: the headline total is the thing people come for, and it should not
 * wait on a year of snapshots to render. A slow history degrades to a spinner under a number that
 * is already on screen.
 */
function HistoryPanel() {
  const { getAccessToken } = useAuth();
  const history = useQuery({
    queryKey: ["portfolio", "history"],
    queryFn: () => pricesApi.portfolioHistory(getAccessToken),
  });

  if (history.isLoading) return <CircularProgress size={20} />;
  if (history.isError || !history.data) return null;

  const data = history.data;
  if (!data.points.length) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6">History</Typography>
        <Typography variant="body2" color="text.secondary">
          Your collection is recorded once a day. The chart appears once there are a few days of
          it — nothing is lost in the meantime.
        </Typography>
      </Paper>
    );
  }

  const pnl = data.profit_and_loss;

  return (
    <Stack spacing={3}>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>Value over time</Typography>
        <ValueHistory points={data.points} pricesStartOn={data.prices_start_on} />
      </Paper>

      {pnl && pnl.covered_items > 0 ? (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6">Profit and loss</Typography>
          <Stack direction="row" spacing={2} sx={{ alignItems: "baseline", mt: 1 }}>
            <Typography
              variant="h4"
              sx={{ color: pnl.gain_cents >= 0 ? "success.main" : "error.main" }}
            >
              {pnl.gain_cents >= 0 ? "+" : ""}{formatMoney(pnl.gain_cents, "EUR")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              on {formatMoney(pnl.cost_cents, "EUR")} paid
            </Typography>
          </Stack>
          {/* Never shown without its coverage. An unrealised gain over a third of a collection
              is a different claim from one over all of it, and rendering them identically is how
              a partial figure gets read as a complete one. */}
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Over {pnl.covered_items} of {pnl.covered_items + pnl.uncovered_items} holdings —{" "}
            {Math.round(pnl.coverage * 100)}% have a recorded cost.{" "}
            {pnl.uncovered_items > 0
              ? "The rest are excluded rather than assumed to have cost nothing."
              : ""}
          </Typography>
        </Paper>
      ) : null}

      {data.best.length ? (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>What your collection is made of</Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            By contribution to the total, so a common held forty times can outrank a single holo.
          </Typography>
          <Stack spacing={0.5} sx={{ mt: 1 }}>
            {data.best.map((p) => (
              <Stack key={p.printing_id} direction="row" spacing={2}
                     sx={{ alignItems: "baseline" }}>
                <Typography sx={{ fontSize: 14, flex: 1 }}>{p.name}</Typography>
                <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
                  {p.set_code} · ×{p.quantity}
                </Typography>
                <Typography sx={{ fontSize: 14, fontWeight: 600 }}>
                  {formatMoney(p.contribution_cents, "EUR")}
                </Typography>
              </Stack>
            ))}
          </Stack>
        </Paper>
      ) : null}
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
