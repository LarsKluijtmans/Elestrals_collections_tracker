import { useAuth } from "@lars-kluijtmans/react-auth";
import { LoginForm } from "@lars-kluijtmans/react-login";
import { Box, CircularProgress } from "@mui/material";
import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { registerTokenGetter } from "../api/backend";
import { authConfig } from "../authConfig";
import { useBranding } from "../branding/BrandingThemeProvider";
import { DashboardPage } from "../pages/Dashboard";
import {
  AddCardsPage, CollectionPage, ImportExportPage, NotFoundPage,
  Placeholder, SealedPage, SetsPage, WishlistPage,
} from "../pages/Placeholder";
import { AppShell } from "./AppShell";
import { ErrorBoundary } from "./ErrorBoundary";
import { PlatformUnavailable } from "./PlatformUnavailable";

// Auth state decides what renders: a spinner while resolving, the "platform unavailable"
// screen if login-api cannot be reached at all, the embedded <LoginForm> when signed out,
// and the routed app shell when signed in.
//
// Because login is embedded rather than a redirect, the URL is untouched throughout — so
// pasting a deep link, signing in, and landing on that page works with no return-path state.
export function Gate() {
  const { isAuthenticated, isLoading, completeLogin, getAccessToken } = useAuth();
  const { branding } = useBranding();
  const [reachable, setReachable] = useState<boolean | null>(null);

  // Registered once so modules outside the tree (ErrorBoundary) can call the backend
  // without threading a token getter through every component.
  useEffect(() => {
    registerTokenGetter(getAccessToken);
  }, [getAccessToken]);

  // login-api is the ONE hard dependency. Everything else degrades to a reduced feature.
  useEffect(() => {
    let active = true;
    fetch(`${authConfig.authApiUrl.replace(/\/$/, "")}/login/v1/.well-known/jwks.json`)
      .then((r) => active && setReachable(r.ok))
      .catch(() => active && setReachable(false));
    return () => {
      active = false;
    };
  }, []);

  if (isLoading || reachable === null) {
    return (
      <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!reachable && !isAuthenticated) {
    return <PlatformUnavailable onRetry={() => window.location.reload()} />;
  }

  if (!isAuthenticated) {
    return (
      <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh", p: 4 }}>
        <Box sx={{ width: "100%", maxWidth: 420 }}>
          <LoginForm
            config={authConfig}
            branding={branding}
            onCode={(code, verifier) => completeLogin(code, verifier)}
            onAuthenticated={() => undefined}
          />
        </Box>
      </Box>
    );
  }

  return (
    <AppShell>
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/collection" element={<CollectionPage />} />
          <Route path="/collection/add" element={<AddCardsPage />} />
          <Route path="/collection/add/set/:setCode" element={<AddCardsPage />} />
          <Route path="/sets" element={<SetsPage />} />
          <Route path="/sets/:code" element={<SetsPage />} />
          <Route path="/cards/:id" element={<Placeholder title="Card" bolt="bolt 003" />} />
          <Route path="/sealed" element={<SealedPage />} />
          <Route path="/wishlist" element={<WishlistPage />} />
          <Route path="/import-export" element={<ImportExportPage />} />
          <Route path="/settings/profile" element={<DashboardPage />} />
          <Route
            path="/settings/notifications"
            element={<Placeholder title="Notifications" bolt="bolt 009" />}
          />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </ErrorBoundary>
    </AppShell>
  );
}
