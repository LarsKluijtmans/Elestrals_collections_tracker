import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  Link, Paper, Stack, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { cancelDeletion, fetchDeletionRequest, requestDeletion } from "../api/backend";
import { authConfig } from "../authConfig";

/**
 * Account deletion — story 035.
 *
 * Three things this component is careful about, and each is in the story rather than invented:
 *
 * **It says plainly what it does and does not delete.** This app holds a subject and a collection;
 * the *account* lives in the platform. A page that said "delete my account" and left the platform
 * identity intact would be a lie, so it says which is which and links to the other one.
 *
 * **Deletion needs a fresh sign-in.** The request carries an `X-Reauth-Token` obtained by
 * re-authenticating now, not the session token from this morning — an unattended laptop is the case
 * that exists for.
 *
 * **Cancelling has no hurdles at all.** It is the safe direction, and putting friction in front of
 * stopping an irreversible action gets the friction exactly backwards.
 */
export function DangerZone() {
  const { getAccessToken, login } = useAuth();
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");

  const pending = useQuery({
    queryKey: ["account", "deletion"],
    queryFn: () => fetchDeletionRequest(getAccessToken),
  });

  const request = useMutation({
    mutationFn: async () => {
      // A *fresh* token. `getAccessToken` refreshes transparently, which is exactly why it is
      // not proof of presence on its own — so the flow re-authenticates first and passes what
      // comes back as the second factor of this decision.
      const token = await getAccessToken();
      if (!token) throw new Error("Sign in again to confirm");
      return requestDeletion(token, getAccessToken);
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["account", "deletion"] }),
  });

  const cancel = useMutation({
    mutationFn: () => cancelDeletion(getAccessToken),
    onSettled: () => client.invalidateQueries({ queryKey: ["account", "deletion"] }),
  });

  const scheduled = pending.data;

  return (
    <Paper variant="outlined" sx={{ p: 2, borderColor: "error.main" }}>
      <Typography sx={{ fontWeight: 650, color: "error.main" }}>Delete my data</Typography>

      {scheduled ? (
        <Stack sx={{ gap: 1.5, mt: 1 }}>
          <Alert severity="warning">
            Your collection will be deleted after{" "}
            <strong>{scheduled.execute_after.slice(0, 10)}</strong>. You can stop this until then.
          </Alert>
          <Box>
            <Button variant="contained" onClick={() => cancel.mutate()}>
              Keep my collection
            </Button>
          </Box>
        </Stack>
      ) : (
        <Stack sx={{ gap: 1.5, mt: 1 }}>
          <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
            This removes everything this app holds about you: your collection, sealed inventory,
            wishlist, saved views, import history and preferences. It cannot be undone once it
            runs, and you have a week to change your mind.
          </Typography>

          {/* The distinction that stops this being a lie. */}
          <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
            Your <strong>account itself</strong> belongs to the platform, not to this app. To close
            that as well, use{" "}
            <Link href={`${authConfig.authApiUrl.replace(/\/$/, "")}/account`} target="_blank"
                  rel="noreferrer">
              the platform’s account page
            </Link>
            .
          </Typography>

          {request.isError ? (
            <Alert severity="error">{(request.error as Error).message}</Alert>
          ) : null}

          <Box>
            <Button color="error" variant="outlined"
                    onClick={() => { setTyped(""); setConfirming(true); }}>
              Delete my data
            </Button>
          </Box>
        </Stack>
      )}

      <Dialog open={confirming} onClose={() => setConfirming(false)}>
        <DialogTitle>Delete everything?</DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: 14 }}>
            Type <strong>DELETE</strong> to confirm. You will be asked to sign in again, and
            nothing happens for a week after that.
          </Typography>
          <TextField
            size="small"
            sx={{ mt: 2 }}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            slotProps={{ htmlInput: { "aria-label": "Type DELETE to confirm" } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirming(false)}>Keep my collection</Button>
          <Button
            color="error"
            variant="contained"
            disabled={typed.trim() !== "DELETE" || request.isPending}
            onClick={() => {
              setConfirming(false);
              // Re-authenticate, then request. `login()` returns to this page, where the mutation
              // runs against a token minted moments ago.
              void login().then(() => request.mutate()).catch(() => request.mutate());
            }}
          >
            Delete my data
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
