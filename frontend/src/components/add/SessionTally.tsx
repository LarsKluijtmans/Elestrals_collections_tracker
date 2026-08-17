import { Alert, Button, Chip, Divider, Paper, Stack, Tooltip, Typography } from "@mui/material";
import { describe, useAddSession } from "../../session/AddSessionContext";
import { UNDO_LIMIT } from "../../session/types";

/**
 * The running tally, the last five adds, and undo.
 *
 * Pending adds are counted. That is what optimistic means, and it is the point: the number moves
 * on the keystroke, not on the response, so a collector never waits to see that their card
 * landed.
 *
 * The undo cap is **stated on screen**. "20 most recent" answers "why can I not undo that one"
 * where the collector is standing, rather than in a code comment they will never read.
 */
export function SessionTally() {
  const { tally, recent, undo, canUndoRecord } = useAddSession();

  return (
    <Paper variant="outlined" sx={{ p: 2, minWidth: 280 }}>
      <Stack sx={{ gap: 1 }}>
        <Typography sx={{ fontSize: 12, color: "text.disabled", textTransform: "uppercase" }}>
          This session
        </Typography>
        <Stack direction="row" sx={{ gap: 3, alignItems: "baseline" }}>
          <Stack>
            <Typography sx={{ fontSize: 28, fontWeight: 650, lineHeight: 1 }}>
              {tally.quantity}
            </Typography>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>cards</Typography>
          </Stack>
          <Stack>
            <Typography sx={{ fontSize: 20, fontWeight: 600, lineHeight: 1 }}>
              {tally.adds}
            </Typography>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>adds</Typography>
          </Stack>
        </Stack>

        <Divider sx={{ my: 1 }} />

        {recent.length === 0 ? (
          <Typography sx={{ fontSize: 13, color: "text.disabled" }}>
            Nothing added yet. Start typing.
          </Typography>
        ) : (
          <Stack sx={{ gap: 0.5 }}>
            {recent.map((record) => {
              const verdict = canUndoRecord(record);
              return (
                <Stack
                  key={record.id}
                  direction="row"
                  sx={{ gap: 1, alignItems: "center", justifyContent: "space-between" }}
                >
                  <Typography
                    sx={{
                      fontSize: 13,
                      textDecoration: record.state === "undone" ? "line-through" : "none",
                      color:
                        record.state === "failed"
                          ? "error.main"
                          : record.state === "undone"
                            ? "text.disabled"
                            : "text.primary",
                    }}
                  >
                    {describe(record)}
                  </Typography>

                  <Stack direction="row" sx={{ gap: 0.5, alignItems: "center" }}>
                    {record.state === "pending" && (
                      <Chip size="small" variant="outlined" label="saving" />
                    )}
                    {record.state === "undone" ? null : (
                      <Tooltip title={verdict.allowed ? "Undo this add" : (verdict.reason ?? "")}>
                        {/* Disabled rather than hidden while pending, so the list does not shift
                            under the cursor as requests resolve. */}
                        <span>
                          <Button
                            size="small"
                            disabled={!verdict.allowed}
                            onClick={() => void undo(record.id)}
                          >
                            Undo
                          </Button>
                        </span>
                      </Tooltip>
                    )}
                  </Stack>
                </Stack>
              );
            })}
          </Stack>
        )}

        {/* Failures are shown here as well as announced. A collector who does not notice a
            failed add has a wrong collection and no way to find out. */}
        {recent
          .filter((record) => record.reason && record.state !== "undone")
          .map((record) => (
            <Alert key={`${record.id}-reason`} severity="warning" sx={{ mt: 1 }}>
              {record.reason}
            </Alert>
          ))}

        <Typography sx={{ fontSize: 11, color: "text.disabled", mt: 1 }}>
          The {UNDO_LIMIT} most recent adds are undoable. The stack is per session and is gone when
          you leave this page.
        </Typography>
      </Stack>
    </Paper>
  );
}
