// login-api is the one hard dependency: no sign-in, no app. Every other platform service
// degrades to a reduced feature. So this screen exists for exactly one failure — and it says
// what is wrong rather than spinning forever.
import { Box, Button, Link, Stack, Typography } from "@mui/material";

export function PlatformUnavailable({ onRetry }: { onRetry?: () => void }) {
  return (
    <Box sx={{ display: "grid", placeItems: "center", minHeight: "70vh", p: 6 }}>
      <Stack spacing={4} sx={{ maxWidth: 480, textAlign: "center" }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>Sign-in is unavailable</Typography>
        <Typography color="text.secondary">
          We cannot reach the authentication service, so signing in is not possible right now.
          This is not a problem with your account, and nothing in your collection is affected.
        </Typography>
        <Stack direction="row" spacing={2} sx={{ justifyContent: "center" }}>
          {onRetry && <Button variant="contained" onClick={onRetry}>Try again</Button>}
          <Button variant="outlined" component={Link} href="/" underline="none">
            Back to start
          </Button>
        </Stack>
        <Typography variant="caption" color="text.disabled">
          Platform status is published on the status page.
        </Typography>
      </Stack>
    </Box>
  );
}
