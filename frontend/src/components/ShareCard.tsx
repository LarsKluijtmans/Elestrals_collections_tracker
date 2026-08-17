import { useAuth } from "@lars-kluijtmans/react-auth";
import { Alert, Box, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { rotateShareToken } from "../api/backend";

/**
 * Sharing a collection — story 033's user-facing half.
 *
 * The three visibilities are genuinely different promises and the copy says which is which, because
 * "link" is the one people misread: an unguessable URL is not access control, it is obscurity that
 * works right up until somebody forwards the link.
 *
 * **Rotating the token is the only revocation a shared URL has** — there is no un-sending one — so
 * it is a visible button rather than something buried behind an edit form.
 */
export function ShareCard({
  visibility, handle,
}: { visibility: "private" | "link" | "public"; handle: string | null }) {
  const { getAccessToken } = useAuth();
  const [token, setToken] = useState<string | null>(null);

  const rotate = useMutation({
    mutationFn: () => rotateShareToken(getAccessToken),
    onSuccess: setToken,
  });

  const shareUrl = token ? `${window.location.origin}/u/shared?token=${token}` : null;

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography sx={{ fontWeight: 650 }}>Sharing</Typography>

      <Stack sx={{ gap: 1.5, mt: 1 }}>
        {visibility === "private" ? (
          <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
            Your collection is private. Nobody but you can see it. Change the visibility above to
            share it.
          </Typography>
        ) : null}

        {visibility === "public" ? (
          <>
            <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
              Your collection is public at{" "}
              <strong>{handle ? `/u/${handle}` : "— set a handle first"}</strong>. Anyone can find
              it, and search engines may index it.
            </Typography>
            {/* Said explicitly, because the difference between "public" and "unlisted" is the
                thing people get wrong when they later regret sharing. */}
            <Alert severity="info">
              Cards, conditions and quantities are shown. What you paid, where things are kept and
              any notes are never included.
            </Alert>
          </>
        ) : null}

        {visibility === "link" ? (
          <>
            <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
              Your collection is reachable only by a private link. It is not listed anywhere and
              search engines are asked not to index it — but <strong>anyone with the link can
              open it</strong>, so treat it like a password.
            </Typography>

            <Box>
              <Button variant="outlined" size="small" disabled={rotate.isPending}
                      onClick={() => rotate.mutate()}>
                {token ? "Make a new link" : "Get a link"}
              </Button>
              <Typography sx={{ fontSize: 12, color: "text.disabled", mt: 0.5 }}>
                Making a new link immediately breaks the old one. That is the only way to take a
                shared link back.
              </Typography>
            </Box>

            {shareUrl ? (
              <TextField
                size="small"
                fullWidth
                value={shareUrl}
                slotProps={{ htmlInput: { readOnly: true, "aria-label": "Your share link" } }}
              />
            ) : null}
          </>
        ) : null}

        {rotate.isError ? (
          <Alert severity="warning">{(rotate.error as Error).message}</Alert>
        ) : null}
      </Stack>
    </Paper>
  );
}
