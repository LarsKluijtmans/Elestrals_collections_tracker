import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, Chip, CircularProgress, Divider, MenuItem, Paper, Stack,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import {
  commitImport, confirmImportRows, remapImport, startImport,
  type CommitResult, type ImportJob,
} from "../api/backend";

/**
 * `/import-export` — the anti-lock-in page. Stories 027, 028 and 029.
 *
 * The flow is upload → **dry run** → commit, and the middle step is the whole point. A mis-mapped
 * column produces visible nonsense in a diff rather than an invisible mess in somebody's
 * collection, and nothing is written until the button at the bottom is pressed.
 *
 * **Fuzzy matches are ticked one at a time.** There is deliberately no "confirm all": that would
 * collapse the matching ladder's least confident rung into a single click somebody makes without
 * reading, which is the failure the ladder exists to prevent.
 */
export function ImportExportPage() {
  const { getAccessToken } = useAuth();
  const [job, setJob] = useState<ImportJob | null>(null);
  const [committed, setCommitted] = useState<CommitResult | null>(null);
  const [ticked, setTicked] = useState<Set<string>>(new Set());

  const upload = useMutation({
    mutationFn: (file: File) => startImport(file, getAccessToken),
    onSuccess: (data) => { setJob(data); setCommitted(null); setTicked(new Set()); },
  });

  const remap = useMutation({
    mutationFn: (mapping: Record<string, string>) => remapImport(job!.id, mapping, getAccessToken),
    onSuccess: setJob,
  });

  const confirm = useMutation({
    mutationFn: () => confirmImportRows(job!.id, [...ticked], getAccessToken),
    onSuccess: (data) => { setJob(data); setTicked(new Set()); },
  });

  const commit = useMutation({
    mutationFn: () => commitImport(job!.id, getAccessToken),
    onSuccess: (result) => { setCommitted(result); setJob(null); },
  });

  return (
    <Stack sx={{ gap: 4, maxWidth: 1000 }}>
      <Box>
        <Typography variant="h1" sx={{ fontSize: 25, fontWeight: 650 }}>Import & export</Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
          Your collection is yours. Take it out as a spreadsheet, edit it, put it back.
        </Typography>
      </Box>

      <ExportPanel />

      <Divider />

      <Box>
        <Typography variant="h2" sx={{ fontSize: 18, fontWeight: 650, mb: 1 }}>Import</Typography>
        <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 2 }}>
          Upload a CSV and you will see exactly what would change before anything is written.
          Comma or semicolon, UTF-8 or the encoding Excel saves on Windows — all handled.
        </Typography>

        <Button variant="outlined" component="label" disabled={upload.isPending}>
          {upload.isPending ? "Reading…" : "Choose a CSV"}
          <input
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate(file);
              event.target.value = "";
            }}
          />
        </Button>

        {upload.isError ? (
          <Alert severity="error" sx={{ mt: 2 }}>{(upload.error as Error).message}</Alert>
        ) : null}
      </Box>

      {committed ? (
        <Alert severity="success">
          Imported {committed.added} new {committed.added === 1 ? "holding" : "holdings"} and
          updated {committed.updated}.
          {committed.skipped
            ? ` ${committed.skipped} row${committed.skipped === 1 ? "" : "s"} skipped.`
            : ""}
        </Alert>
      ) : null}

      {job ? (
        <DryRun
          job={job}
          ticked={ticked}
          busy={remap.isPending || confirm.isPending || commit.isPending}
          error={commit.isError ? (commit.error as Error).message : null}
          onRemap={(mapping) => remap.mutate(mapping)}
          onTick={(id) => setTicked((current) => {
            const next = new Set(current);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
          })}
          onConfirm={() => confirm.mutate()}
          onCommit={() => commit.mutate()}
        />
      ) : null}
    </Stack>
  );
}

function ExportPanel() {
  return (
    <Box>
      <Typography variant="h2" sx={{ fontSize: 18, fontWeight: 650, mb: 1 }}>Export</Typography>
      <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 2 }}>
        Plain CSV, one file each. These are the exact format the importer reads, so anything you
        export here can come straight back in.
      </Typography>
      <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap" }}>
        {/* Plain links, so the browser streams the download straight to disk rather than the
            page holding a 10,000-row blob in memory to hand back to it. */}
        <Button variant="outlined" href="/api/v1/export/collection">Collection</Button>
        <Button variant="outlined" href="/api/v1/export/sealed">Sealed</Button>
        <Button variant="outlined" href="/api/v1/export/wishlist">Wishlist</Button>
      </Stack>
      <Typography sx={{ fontSize: 12, color: "text.disabled", mt: 1 }}>
        To export only part of your collection, filter it on the collection page and use the
        export button there.
      </Typography>
    </Box>
  );
}

const OUR_FIELDS = [
  "printing_id", "set_code", "collector_number", "name", "finish", "language",
  "edition", "condition", "quantity",
];

function DryRun({
  job, ticked, busy, error, onRemap, onTick, onConfirm, onCommit,
}: {
  job: ImportJob;
  ticked: Set<string>;
  busy: boolean;
  error: string | null;
  onRemap: (mapping: Record<string, string>) => void;
  onTick: (id: string) => void;
  onConfirm: () => void;
  onCommit: () => void;
}) {
  const headers = [...new Set(job.rows.flatMap((r) => Object.keys(r.raw)))];
  const problems = job.rows.filter(
    (r) => r.verdict === "rejected" || r.verdict === "needs_confirmation",
  );

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack sx={{ gap: 2 }}>
        <Box>
          <Typography sx={{ fontWeight: 650 }}>{job.filename}</Typography>
          <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
            {/* Reported so a mangled preview has a diagnosable cause. "We read this as CP1252"
                is a fixable complaint; "it looks wrong" is not. */}
            {job.total_rows.toLocaleString()} rows · read as {job.encoding} ·
            {job.delimiter === ";" ? " semicolon" : job.delimiter === "\t" ? " tab" : " comma"}
            -separated
          </Typography>
        </Box>

        <Stack direction="row" sx={{ gap: 2, flexWrap: "wrap" }}>
          <Count label="To add" value={job.add_count} tone="success" />
          <Count label="To update" value={job.update_count} tone="info" />
          <Count label="Need confirming" value={job.needs_confirmation_count} tone="warning" />
          <Count label="Rejected" value={job.rejected_count} tone="error" />
        </Stack>

        <Alert severity="info">
          Nothing has been written yet. This is what <em>would</em> happen.
        </Alert>

        <Box>
          <Typography sx={{ fontSize: 13, fontWeight: 600, mb: 1 }}>Column mapping</Typography>
          <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap" }}>
            {OUR_FIELDS.map((field) => (
              <TextField
                key={field}
                select
                size="small"
                label={field}
                value={job.mapping[field] ?? ""}
                sx={{ minWidth: 170 }}
                onChange={(event) => onRemap({
                  ...job.mapping,
                  [field]: event.target.value,
                })}
              >
                <MenuItem value="">— not mapped —</MenuItem>
                {headers.map((header) => (
                  <MenuItem key={header} value={header}>{header}</MenuItem>
                ))}
              </TextField>
            ))}
          </Stack>
        </Box>

        {problems.length ? (
          <Box>
            <Typography sx={{ fontSize: 13, fontWeight: 600, mb: 1 }}>
              Rows that need you
            </Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Row</TableCell>
                  <TableCell>What we found</TableCell>
                  <TableCell>Why</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {problems.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.line_number}</TableCell>
                    <TableCell sx={{ fontSize: 12 }}>
                      {Object.values(row.raw).filter(Boolean).slice(0, 3).join(" · ")}
                    </TableCell>
                    <TableCell sx={{ fontSize: 12 }}>
                      {row.verdict === "needs_confirmation" ? (
                        <>
                          Matched by name only
                          {row.match_score !== null
                            ? ` (${Math.round(row.match_score * 100)}% similar)`
                            : ""}
                        </>
                      ) : (
                        row.reason
                      )}
                    </TableCell>
                    <TableCell>
                      {row.verdict === "needs_confirmation" ? (
                        row.confirmed ? (
                          <Chip size="small" color="success" label="confirmed" />
                        ) : (
                          <Button size="small" onClick={() => onTick(row.id)}>
                            {ticked.has(row.id) ? "Ticked" : "Use this match"}
                          </Button>
                        )
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {job.rows_truncated ? (
              <Typography sx={{ fontSize: 12, color: "text.disabled", mt: 1 }}>
                Showing the first {job.rows.length} rows that need attention.
              </Typography>
            ) : null}
            {ticked.size ? (
              <Button size="small" sx={{ mt: 1 }} disabled={busy} onClick={onConfirm}>
                Confirm {ticked.size} match{ticked.size === 1 ? "" : "es"}
              </Button>
            ) : null}
          </Box>
        ) : null}

        {error ? <Alert severity="error">{error}</Alert> : null}

        <Stack direction="row" sx={{ gap: 2, alignItems: "center" }}>
          <Button variant="contained" disabled={busy} onClick={onCommit}>
            {busy ? <CircularProgress size={18} /> : `Import ${job.add_count + job.update_count} rows`}
          </Button>
          <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
            All or nothing — if any row fails, none of them are written.
          </Typography>
        </Stack>
      </Stack>
    </Paper>
  );
}

function Count({
  label, value, tone,
}: { label: string; value: number; tone: "success" | "info" | "warning" | "error" }) {
  return (
    <Box>
      <Typography
        sx={{
          fontSize: 22, fontWeight: 700, lineHeight: 1,
          color: value ? `${tone}.main` : "text.disabled",
        }}
      >
        {value}
      </Typography>
      <Typography sx={{ fontSize: 12, color: "text.secondary" }}>{label}</Typography>
    </Box>
  );
}
