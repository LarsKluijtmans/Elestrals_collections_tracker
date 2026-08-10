// A thrown component must produce a recoverable page, never a blank screen.
// The error is relayed to our backend (which stamps the validated caller) rather than
// written to logs-api from the browser — the browser has no `logs:write`, and relaying
// through an authenticated endpoint is what makes the attribution trustworthy.
import { Box, Button, Stack, Typography } from "@mui/material";
import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { reportClientEvent } from "../api/backend";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    void reportClientEvent({
      level: "warning",
      message: `render error: ${error.message}`,
      component: "error-boundary",
      context: { componentStack: info.componentStack?.slice(0, 1000) },
    });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <Box sx={{ display: "grid", placeItems: "center", minHeight: "60vh", p: 6 }}>
        <Stack spacing={4} sx={{ maxWidth: 460, textAlign: "center" }}>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>Something broke on this page</Typography>
          <Typography color="text.secondary">
            The rest of the app still works. Reloading usually clears it — if it keeps
            happening, the error has been recorded.
          </Typography>
          <Stack direction="row" spacing={2} sx={{ justifyContent: "center" }}>
            <Button variant="contained" onClick={() => this.setState({ error: null })}>
              Try again
            </Button>
            <Button variant="outlined" onClick={() => window.location.reload()}>
              Reload
            </Button>
          </Stack>
        </Stack>
      </Box>
    );
  }
}
