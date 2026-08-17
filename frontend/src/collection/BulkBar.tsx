import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  MenuItem, Paper, Stack, TextField, Typography,
} from "@mui/material";
import { useState } from "react";
import type { BulkResult } from "../api/backend";

/**
 * Bulk actions — story 022.
 *
 * Two rules from the story shape this component rather than decorate it.
 *
 * **The confirmation names the count**, and for a delete of everything it makes you *type* it. A
 * dialog that says "delete these?" is the one that gets clicked through; a dialog that says
 * "delete 1,247 cards?" is read.
 *
 * **Partial failure is shown, not swallowed.** The result panel names the rows that failed and
 * why, and stays on screen until dismissed — a collector who does not know which of 500 rows
 * failed has an unknown collection.
 */

const CONDITIONS = [
  "mint", "near_mint", "lightly_played", "moderately_played", "heavily_played", "damaged",
];

/** Above this, deleting requires typing the number. Chosen so an ordinary tidy-up is one click
 *  and an accidental select-all-and-delete is not. */
const TYPE_TO_CONFIRM_ABOVE = 20;

export function BulkBar({
  count, busy, result, onEdit, onDelete, onExport, onClear, onDismissResult,
}: {
  count: number;
  busy: boolean;
  result: BulkResult | null;
  onEdit: (fields: { condition?: string; storage_location?: string; is_for_trade?: boolean }) => void;
  onDelete: () => void;
  onExport: () => void;
  onClear: () => void;
  onDismissResult: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [condition, setCondition] = useState("");
  const [location, setLocation] = useState("");
  const [forTrade, setForTrade] = useState<"" | "yes" | "no">("");
  const [typed, setTyped] = useState("");

  const needsTyping = count > TYPE_TO_CONFIRM_ABOVE;
  const canDelete = !needsTyping || typed.trim() === String(count);

  if (count === 0 && !result) return null;

  return (
    <>
      {result ? (
        <Alert
          severity={result.failures.length ? "warning" : "success"}
          onClose={onDismissResult}
          sx={{ mb: 1 }}
        >
          <Typography sx={{ fontSize: 14 }}>
            {result.applied} of {result.requested} applied
            {result.failures.length ? `, ${result.failures.length} failed` : ""}.
          </Typography>
          {/* Named individually. "Some rows failed" leaves a collector unable to fix anything. */}
          {result.failures.length ? (
            <Box component="ul" sx={{ m: 0, mt: 0.5, pl: 2, fontSize: 12 }}>
              {result.failures.slice(0, 10).map((failure) => (
                <li key={failure.item_id}>
                  {failure.item_id.slice(0, 8)}… — {failure.reason}
                </li>
              ))}
              {result.failures.length > 10 ? (
                <li>…and {result.failures.length - 10} more</li>
              ) : null}
            </Box>
          ) : null}
        </Alert>
      ) : null}

      {count > 0 ? (
        <Paper variant="outlined" sx={{ p: 1.5, mb: 1 }}>
          <Stack direction="row" sx={{ gap: 1, alignItems: "center", flexWrap: "wrap" }}>
            <Typography sx={{ fontWeight: 600 }} aria-live="polite">
              {count.toLocaleString()} selected
            </Typography>
            <Button size="small" disabled={busy} onClick={() => setEditing(true)}>Edit</Button>
            <Button size="small" disabled={busy} onClick={onExport}>Export</Button>
            <Button size="small" color="error" disabled={busy}
                    onClick={() => { setTyped(""); setConfirming(true); }}>
              Delete
            </Button>
            <Button size="small" sx={{ ml: "auto" }} onClick={onClear}>Clear selection</Button>
          </Stack>
        </Paper>
      ) : null}

      <Dialog open={editing} onClose={() => setEditing(false)}>
        <DialogTitle>Edit {count.toLocaleString()} cards</DialogTitle>
        <DialogContent>
          <Stack sx={{ gap: 2, pt: 1, minWidth: 320 }}>
            {/* Blank means "leave alone". Setting every field on every selected row would
                overwrite storage locations somebody spent an evening entering. */}
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
              Leave a field blank to leave it unchanged.
            </Typography>
            <TextField select size="small" label="Condition" value={condition}
                       onChange={(e) => setCondition(e.target.value)}>
              <MenuItem value="">Leave unchanged</MenuItem>
              {CONDITIONS.map((c) => (
                <MenuItem key={c} value={c}>{c.replace(/_/g, " ")}</MenuItem>
              ))}
            </TextField>
            <TextField size="small" label="Storage location" value={location}
                       onChange={(e) => setLocation(e.target.value)} />
            <TextField select size="small" label="For trade" value={forTrade}
                       onChange={(e) => setForTrade(e.target.value as "" | "yes" | "no")}>
              <MenuItem value="">Leave unchanged</MenuItem>
              <MenuItem value="yes">Yes</MenuItem>
              <MenuItem value="no">No</MenuItem>
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditing(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => {
              onEdit({
                condition: condition || undefined,
                storage_location: location || undefined,
                is_for_trade: forTrade === "" ? undefined : forTrade === "yes",
              });
              setEditing(false);
            }}
          >
            Apply to {count.toLocaleString()}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={confirming} onClose={() => setConfirming(false)}>
        <DialogTitle>Delete {count.toLocaleString()} cards?</DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: 14 }}>
            This removes {count.toLocaleString()} {count === 1 ? "row" : "rows"} from your
            collection. It cannot be undone from here.
          </Typography>
          {needsTyping ? (
            <TextField
              size="small"
              sx={{ mt: 2 }}
              label={`Type ${count} to confirm`}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
            />
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirming(false)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            disabled={!canDelete}
            onClick={() => { setConfirming(false); onDelete(); }}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
