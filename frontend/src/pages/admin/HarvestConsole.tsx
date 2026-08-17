import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, Chip, CircularProgress, Divider, FormControl, InputLabel, Link,
  MenuItem, Paper, Select, Stack, Tab, Table, TableBody, TableCell, TableHead, TableRow,
  Tabs, TextField, Tooltip, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  harvestApi, statusLabel,
  type ListingFilters, type ListingSummary, type RunSummary, type SourceHealth,
} from "../../api/harvest";
import { formatMoney } from "../../components/MoneyFigure";

/**
 * `/admin/harvest` — the surface the admin-only decision exists for.
 *
 * Under ADR-004 every figure in phase 2 comes from scraped pages of uneven quality, and this is
 * where a human finds out whether that data is worth building a valuation on. It is scheduled
 * before the user-facing price surfaces for exactly that reason: building valuation first would
 * mean discovering a systematic matcher error through somebody's portfolio number.
 *
 * Lazy-loaded and gated before the chunk is requested, so a non-admin never downloads it — see
 * `useIsAdmin`. Hiding it client-side would leave every endpoint path in the bundle.
 */
export default function HarvestConsolePage() {
  const [tab, setTab] = useState(0);
  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Harvest console</Typography>
        <Typography variant="body2" color="text.secondary">
          Raw collection data. Admin only — this is not what collectors see.
        </Typography>
      </Box>

      <Tabs value={tab} onChange={(_, value) => setTab(value)}>
        <Tab label="Sources" />
        <Tab label="Listings" />
        <Tab label="Quality" />
      </Tabs>

      {tab === 0 ? <SourcesPanel /> : null}
      {tab === 1 ? <ListingsPanel /> : null}
      {tab === 2 ? <QualityPanel /> : null}
    </Stack>
  );
}

// --- sources -------------------------------------------------------------------------

function SourcesPanel() {
  const { getAccessToken } = useAuth();
  const client = useQueryClient();
  const sources = useQuery({
    queryKey: ["harvest", "sources"],
    queryFn: () => harvestApi.sources(getAccessToken),
    // While a scan is running the counters move; five seconds is often enough to feel live and
    // rare enough not to hammer a service that is busy scraping.
    refetchInterval: 5_000,
  });

  const trigger = useMutation({
    mutationFn: ({ key, mode }: { key: string; mode: "deep" | "light" }) =>
      harvestApi.triggerScan(getAccessToken, key, mode),
    onSettled: () => client.invalidateQueries({ queryKey: ["harvest"] }),
  });
  const disable = useMutation({
    mutationFn: (key: string) => harvestApi.disableSource(getAccessToken, key),
    onSettled: () => client.invalidateQueries({ queryKey: ["harvest", "sources"] }),
  });
  const release = useMutation({
    mutationFn: (key: string) => harvestApi.clearQuarantine(getAccessToken, key),
    onSettled: () => client.invalidateQueries({ queryKey: ["harvest", "sources"] }),
  });

  if (sources.isLoading) return <CircularProgress />;
  if (sources.isError) return <HarvestUnavailable error={sources.error} />;

  return (
    <Stack spacing={2}>
      {trigger.isError ? (
        <Alert severity="warning">{(trigger.error as Error).message}</Alert>
      ) : null}

      <PipelineControls />

      {sources.data?.map((source) => (
        <Paper key={source.key} sx={{ p: 2 }}>
          <Stack direction="row" spacing={2} sx={{ alignItems: "flex-start", flexWrap: "wrap" }}>
            <Box sx={{ flex: 1, minWidth: 240 }}>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                <Typography variant="h6">{source.name}</Typography>
                <Chip size="small" label={source.access_mode} />
                {source.reports_sold ? (
                  <Tooltip title="Reports completed sales — the only kind that feeds valuation">
                    <Chip size="small" color="success" label="reports sales" />
                  </Tooltip>
                ) : (
                  <Chip size="small" variant="outlined" label="asking prices only" />
                )}
                {source.enabled ? null : <Chip size="small" label="disabled" />}
              </Stack>

              {/* ADR-004 accepts a contractual risk per source. Putting the note and the person
                  who accepted it where an admin sees them every time they look at the pipeline
                  is what keeps "reviewed: yes" from being enough. */}
              {source.tos_review_note ? (
                <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 1 }}>
                  {source.tos_review_note}
                </Typography>
              ) : (
                <Alert severity="error" sx={{ mt: 1 }}>
                  No terms review recorded — this source cannot be enabled.
                </Alert>
              )}
              {source.risk_accepted_by ? (
                <Typography variant="caption" color="text.secondary">
                  Risk accepted by {source.risk_accepted_by}
                  {source.risk_accepted_on ? ` on ${source.risk_accepted_on}` : ""}
                </Typography>
              ) : null}
            </Box>

            <Box sx={{ minWidth: 260 }}>
              <SourceState source={source} />
            </Box>

            <Stack spacing={1} sx={{ minWidth: 160 }}>
              <Button
                size="small"
                variant="outlined"
                disabled={!source.enabled || source.quarantined || trigger.isPending}
                onClick={() => trigger.mutate({ key: source.key, mode: "light" })}
              >
                Run light scan
              </Button>
              <Button
                size="small"
                variant="outlined"
                disabled={!source.enabled || source.quarantined || trigger.isPending}
                onClick={() => trigger.mutate({ key: source.key, mode: "deep" })}
              >
                Run deep scan
              </Button>
              {source.quarantined ? (
                <Button size="small" color="warning" onClick={() => release.mutate(source.key)}>
                  Clear quarantine
                </Button>
              ) : null}
              {source.enabled ? (
                <Button size="small" color="error" onClick={() => disable.mutate(source.key)}>
                  Disable
                </Button>
              ) : null}
            </Stack>
          </Stack>

          <Divider sx={{ my: 2 }} />
          <Stack direction="row" spacing={4} sx={{ flexWrap: "wrap" }}>
            <RunCard title="Last deep scan" run={source.last_deep_run} neverRun={source.never_run} />
            <RunCard title="Last light scan" run={source.last_light_run} neverRun={source.never_run} />
            <Box>
              <Typography variant="overline" color="text.secondary">
                Accept rate
              </Typography>
              <AcceptRate label="deep" points={source.accept_rate_deep} />
              <AcceptRate label="light" points={source.accept_rate_light} />
            </Box>
            <Box>
              <Typography variant="overline" color="text.secondary">
                Live listings
              </Typography>
              <Typography variant="h6">{source.live_listings}</Typography>
            </Box>
          </Stack>
        </Paper>
      ))}
    </Stack>
  );
}

/**
 * Running the rest of the pipeline by hand.
 *
 * A scan writes **observations**. Nothing a collector sees moves until `price_daily` is recomputed,
 * and that used to happen only on the beat schedule — so triggering a scan to check a fix meant
 * waiting out the interval or shelling into a container. These two buttons are what make the
 * manual path actually usable end to end: scan → recompute → look at `/prices`.
 *
 * The recompute is synchronous and window-bounded (the cap comes from the API rather than being
 * repeated here). A full-history rebuild is deliberately not offered: it is a job, not a request,
 * and it lives on the CLI as `python -m app.harvest --rollup`.
 */
function PipelineControls() {
  const { getAccessToken } = useAuth();
  const client = useQueryClient();
  const [sinceDays, setSinceDays] = useState(7);

  const rollup = useMutation({
    mutationFn: () => harvestApi.recomputeRollup(getAccessToken, sinceDays),
    // Prices and coverage both read what this just rewrote.
    onSettled: () => client.invalidateQueries({ queryKey: ["harvest"] }),
  });
  const sweep = useMutation({
    mutationFn: () => harvestApi.sweepStaleRuns(getAccessToken),
    onSettled: () => client.invalidateQueries({ queryKey: ["harvest"] }),
  });

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="overline" color="text.secondary">
        Pipeline
      </Typography>
      <Stack
        direction="row"
        spacing={2}
        sx={{ alignItems: "flex-start", flexWrap: "wrap", mt: 1 }}
      >
        <TextField
          select
          size="small"
          label="Recompute"
          value={sinceDays}
          onChange={(event) => setSinceDays(Number(event.target.value))}
          sx={{ minWidth: 150 }}
        >
          <MenuItem value={1}>Today</MenuItem>
          <MenuItem value={7}>Last 7 days</MenuItem>
          <MenuItem value={30}>Last 30 days</MenuItem>
          <MenuItem value={90}>Last 90 days</MenuItem>
        </TextField>

        <Button
          size="small"
          variant="contained"
          disabled={rollup.isPending}
          onClick={() => rollup.mutate()}
        >
          {rollup.isPending ? "Recomputing…" : "Recompute prices"}
        </Button>

        <Tooltip title="Fail runs orphaned by a deploy, so a stuck 'running' row stops refusing a new scan">
          <Button size="small" disabled={sweep.isPending} onClick={() => sweep.mutate()}>
            Sweep stale runs
          </Button>
        </Tooltip>

        <Box sx={{ flex: 1, minWidth: 260 }}>
          {rollup.isError ? (
            <Alert severity="warning">{(rollup.error as Error).message}</Alert>
          ) : null}
          {sweep.isError ? (
            <Alert severity="warning">{(sweep.error as Error).message}</Alert>
          ) : null}

          {rollup.data ? (
            <Alert severity={rollup.data.days === 0 ? "info" : "success"}>
              {rollup.data.days === 0
                ? `No observations since ${rollup.data.since} — nothing to publish.`
                : `Recomputed ${rollup.data.days} day${rollup.data.days === 1 ? "" : "s"} ` +
                  `since ${rollup.data.since}: ${rollup.data.rows} published, ` +
                  `${rollup.data.excluded} point${rollup.data.excluded === 1 ? "" : "s"} ` +
                  `excluded as outliers.`}
            </Alert>
          ) : null}
          {sweep.data ? (
            <Alert severity={sweep.data.swept === 0 ? "info" : "warning"}>
              {sweep.data.swept === 0
                ? `Nothing older than ${sweep.data.stale_after_minutes} minutes was stuck.`
                : `Swept ${sweep.data.swept} stale run${sweep.data.swept === 1 ? "" : "s"} to failed.`}
            </Alert>
          ) : null}
        </Box>
      </Stack>

      <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 1.5 }}>
        The rollup also runs on a schedule. Recompute here after a manual scan to see its prices
        without waiting. For a full rebuild over all history, run{" "}
        <code>python -m app.harvest --rollup</code>.
      </Typography>
    </Paper>
  );
}

/** A quarantined source must look different from one that is merely finding nothing, and a
 *  source that has never run must look different from both. */
function SourceState({ source }: { source: SourceHealth }) {
  if (source.quarantined) {
    return (
      <Alert severity="error" icon={false}>
        <strong>Quarantined</strong> — {source.quarantine_reason ?? "blocked"}
        <br />
        Retrying after {source.quarantined_until ? formatWhen(source.quarantined_until) : "backoff"}
        {source.quarantine_level > 1 ? ` (level ${source.quarantine_level})` : ""}
      </Alert>
    );
  }
  if (source.never_run) {
    return <Alert severity="info" icon={false}>Never run.</Alert>;
  }
  return <Alert severity="success" icon={false}>Healthy.</Alert>;
}

function RunCard({
  title, run, neverRun,
}: { title: string; run: RunSummary | null; neverRun: boolean }) {
  return (
    <Box sx={{ minWidth: 220 }}>
      <Typography variant="overline" color="text.secondary">{title}</Typography>
      {run === null ? (
        <Typography variant="body2" color="text.secondary">
          {neverRun ? "never run" : "not in this mode yet"}
        </Typography>
      ) : (
        <>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Chip size="small" label={run.status} color={statusColour(run.status)} />
            <Typography variant="caption">{formatWhen(run.started_at)}</Typography>
            {run.triggered_by !== "schedule" ? (
              <Chip size="small" variant="outlined" label={run.triggered_by} />
            ) : null}
          </Stack>
          <Typography variant="caption" color="text.secondary" component="p">
            {run.queries} queries · {run.fetched} fetched · {run.accepted} priced ·{" "}
            {run.rejected} rejected · {run.discovered} new · {run.ended} ended
          </Typography>
          {run.error_summary ? (
            <Tooltip title={run.error_summary}>
              <Typography variant="caption" color="error" noWrap sx={{ display: "block", maxWidth: 220 }}>
                {run.error_summary.split("\n")[0]}
              </Typography>
            </Tooltip>
          ) : null}
        </>
      )}
    </Box>
  );
}

/** Trended, and per mode. A deep scan's accept rate is legitimately lower than a light scan's —
 *  it asks broader questions — and merging them hides both signals. */
function AcceptRate({ label, points }: { label: string; points: [string, number][] }) {
  if (points.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        {label}: no runs
      </Typography>
    );
  }
  const latest = points[points.length - 1][1];
  const first = points[0][1];
  const falling = points.length > 2 && latest < first * 0.6;
  return (
    <Typography variant="body2" color={falling ? "error" : "text.primary"}>
      {label}: {(latest * 100).toFixed(0)}%
      {falling ? " — falling, check the connector" : ""}
    </Typography>
  );
}

// --- listings ------------------------------------------------------------------------

function ListingsPanel() {
  const { getAccessToken } = useAuth();
  const [filters, setFilters] = useState<ListingFilters>({ limit: 50, offset: 0 });

  const listings = useQuery({
    queryKey: ["harvest", "listings", filters],
    queryFn: () => harvestApi.listings(getAccessToken, filters),
  });

  const set = (patch: Partial<ListingFilters>) =>
    setFilters((current) => ({ ...current, ...patch, offset: 0 }));

  return (
    <Stack spacing={2}>
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" spacing={2} sx={{ flexWrap: "wrap", alignItems: "center" }}>
          <TextField
            size="small" label="Search titles" sx={{ minWidth: 220 }}
            onChange={(e) => set({ search: e.target.value || undefined })}
          />
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Match</InputLabel>
            <Select
              label="Match" defaultValue=""
              onChange={(e) =>
                set({ matched: e.target.value === "" ? undefined : e.target.value === "yes" })
              }
            >
              <MenuItem value="">Any</MenuItem>
              <MenuItem value="yes">Matched</MenuItem>
              {/* The queue of things the catalog or the matcher is missing. One click, because
                  it is the most useful view in the console and nobody will dig for it. */}
              <MenuItem value="no">Unmatched</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Status</InputLabel>
            <Select
              label="Status" defaultValue=""
              onChange={(e) => set({ status: e.target.value || undefined })}
            >
              <MenuItem value="">Any</MenuItem>
              <MenuItem value="active">Live</MenuItem>
              <MenuItem value="ended_sold">Sold</MenuItem>
              <MenuItem value="ended_unsold">Ended, unsold</MenuItem>
              <MenuItem value="ended_unknown">Ended, reason unknown</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Confidence</InputLabel>
            <Select
              label="Confidence" defaultValue=""
              onChange={(e) => {
                const value = e.target.value;
                if (value === "") set({ min_confidence: undefined, max_confidence: undefined });
                else if (value === "under") set({ min_confidence: undefined, max_confidence: 0.7 });
                else set({ min_confidence: 0.7, max_confidence: undefined });
              }}
            >
              <MenuItem value="">Any</MenuItem>
              <MenuItem value="over">Above the floor</MenuItem>
              <MenuItem value="under">Under the floor</MenuItem>
            </Select>
          </FormControl>
        </Stack>
      </Paper>

      {listings.isError ? <HarvestUnavailable error={listings.error} /> : null}
      {listings.isLoading ? <CircularProgress /> : null}

      {listings.data ? (
        <Paper>
          <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
            {listings.data.total} listing(s)
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>Matched to</TableCell>
                <TableCell>Why</TableCell>
                <TableCell align="right">Price</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Source</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {listings.data.items.map((listing) => (
                <ListingRow key={listing.id} listing={listing} />
              ))}
            </TableBody>
          </Table>
          {listings.data.items.length === 0 ? (
            <Typography color="text.secondary" sx={{ p: 2 }}>
              No listings match these filters.
            </Typography>
          ) : null}
        </Paper>
      ) : null}
    </Stack>
  );
}

function ListingRow({ listing }: { listing: ListingSummary }) {
  return (
    <TableRow hover>
      <TableCell sx={{ maxWidth: 320 }}>
        <Link href={listing.url} target="_blank" rel="noreferrer noopener" underline="hover">
          {listing.title}
        </Link>
      </TableCell>
      <TableCell>
        {listing.product_label ?? (
          <Typography variant="body2" color="text.secondary">unmatched</Typography>
        )}
      </TableCell>
      {/* The most useful column in the console: an unmatched listing is a lead, and this is how
          you tell a missing catalog row from a matcher gap without re-running anything. */}
      <TableCell sx={{ maxWidth: 280 }}>
        <Typography variant="caption" color="text.secondary">
          {listing.match_note ?? "—"}
          {listing.match_confidence !== null
            ? ` (${listing.match_confidence.toFixed(2)})`
            : ""}
        </Typography>
      </TableCell>
      <TableCell align="right">{formatMoney(listing.price_cents, listing.currency)}</TableCell>
      <TableCell>
        <Chip
          size="small"
          variant={listing.status === "active" ? "filled" : "outlined"}
          label={statusLabel(listing.status)}
        />
      </TableCell>
      <TableCell>{listing.source_key}</TableCell>
    </TableRow>
  );
}

// --- quality -------------------------------------------------------------------------

function QualityPanel() {
  const { getAccessToken } = useAuth();
  const coverage = useQuery({
    queryKey: ["harvest", "coverage"],
    queryFn: () => harvestApi.coverage(getAccessToken, 7),
  });

  if (coverage.isLoading) return <CircularProgress />;
  if (coverage.isError) return <HarvestUnavailable error={coverage.error} />;
  const report = coverage.data!;

  const ratio = report.tracked_printings
    ? report.priced_printings / report.tracked_printings
    : 0;

  return (
    <Stack spacing={2}>
      <Paper sx={{ p: 2 }}>
        <Typography variant="overline" color="text.secondary">
          Coverage, last {report.window_days} days
        </Typography>
        <Typography variant="h4">{(ratio * 100).toFixed(1)}%</Typography>
        {/* The denominator is shown deliberately: a high ratio over an incomplete catalog is not
            the same achievement as a high ratio over a complete one, and ADR-001 left the seed
            incomplete. */}
        <Typography variant="body2" color="text.secondary">
          {report.priced_printings} of {report.tracked_printings} tracked printings have a sold
          observation
        </Typography>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="overline" color="text.secondary">
          What is not matching
        </Typography>
        <Stack direction="row" spacing={4} sx={{ mt: 1, flexWrap: "wrap" }}>
          {/* Split on purpose. "No catalog card" points at the catalog — often a real finding,
              since discovering products we do not have is one of the two things a deep scan is
              for. "Under the floor" points at the matcher. Merging them into one number hides
              which of the two you should be working on. */}
          <Box>
            <Typography variant="h5">{report.unmatched_no_catalog}</Typography>
            <Typography variant="body2" color="text.secondary">
              no catalog card found — check the catalog
            </Typography>
          </Box>
          <Box>
            <Typography variant="h5">{report.unmatched_under_floor}</Typography>
            <Typography variant="body2" color="text.secondary">
              matched but under the floor — check the matcher
            </Typography>
          </Box>
        </Stack>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="overline" color="text.secondary">
          Top rejection reasons
        </Typography>
        <Table size="small">
          <TableBody>
            {report.top_rejections.map((row) => (
              <TableRow key={row.reason}>
                <TableCell>{row.reason}</TableCell>
                <TableCell align="right">{row.count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {report.top_rejections.length === 0 ? (
          <Typography color="text.secondary">Nothing rejected yet.</Typography>
        ) : null}
      </Paper>
    </Stack>
  );
}

// --- shared --------------------------------------------------------------------------

/** harvest-api being unreachable is a normal state, not a crash: it is a separate service that
 *  can be down, blocked or mid-deploy while the collection tracker is perfectly fine. */
function HarvestUnavailable({ error }: { error: unknown }) {
  return (
    <Alert severity="warning">
      <strong>Harvest service unavailable.</strong> Collectors are unaffected — price surfaces
      serve the last published rollups. {(error as Error)?.message}
    </Alert>
  );
}

function statusColour(status: RunSummary["status"]) {
  if (status === "success") return "success" as const;
  if (status === "partial") return "warning" as const;
  if (status === "failed") return "error" as const;
  return "info" as const;
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString();
}
