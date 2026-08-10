import { useAuth } from "@lars-kluijtmans/react-auth";
import { LoginForm } from "@lars-kluijtmans/react-login";
import { Box, CircularProgress } from "@mui/material";
import { useEffect, useState, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { registerTokenGetter } from "../api/backend";
import { authConfig } from "../authConfig";
import { useBranding } from "../branding/BrandingThemeProvider";
import { AdminCatalogPage } from "../pages/AdminCatalog";
import { CardDetailPage } from "../pages/CardDetail";
import { DashboardPage } from "../pages/Dashboard";
import {
  AddCardsPage, CollectionPage, ImportExportPage, NotFoundPage,
  Placeholder, SealedPage, WishlistPage,
} from "../pages/Placeholder";
import { SetDetailPage } from "../pages/SetDetail";
import { SetsPage } from "../pages/Sets";
import { AppShell } from "./AppShell";
import { ErrorBoundary } from "./ErrorBoundary";
import { PlatformUnavailable } from "./PlatformUnavailable";

// Auth state decides what renders: a spinner while resolving, the "platform unavailable"
// screen if login-api cannot be reached at all, and otherwise the routed app shell.
//
// The shell renders for **anonymous visitors too**. `/sets`, `/sets/:code` and `/cards/:id`
// are public (api-conventions.md), and story 010–012 require them to work signed out — so
// the login form is scoped to the routes that actually need a session, not hoisted over the
// whole application.
//
// Because login is embedded rather than a redirect, the URL is untouched throughout: pasting
// a deep link, signing in, and landing on that page works with no return-path state.
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

  function SignInPrompt() {
    return (
      <Box sx={{ display: "grid", placeItems: "center", minHeight: "60vh", p: 4 }}>
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

  /** Wraps a route that needs a session. Renders the embedded form in place, so the URL —
   *  and therefore the deep link — survives sign-in untouched. */
  function RequireAuth({ children }: { children: ReactNode }) {
    return isAuthenticated ? <>{children}</> : <SignInPrompt />;
  }

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

  return (
    <AppShell>
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<Navigate to={isAuthenticated ? "/dashboard" : "/sets"} replace />} />

          {/* Public — no session required. */}
          <Route path="/sets" element={<SetsPage />} />
          <Route path="/sets/:code" element={<SetDetailPage />} />
          <Route path="/cards/:id" element={<CardDetailPage />} />

          {/* Authenticated. */}
          <Route path="/dashboard" element={<RequireAuth><DashboardPage /></RequireAuth>} />
          <Route path="/collection" element={<RequireAuth><CollectionPage /></RequireAuth>} />
          <Route path="/collection/add" element={<RequireAuth><AddCardsPage /></RequireAuth>} />
          <Route
            path="/collection/add/set/:setCode"
            element={<RequireAuth><AddCardsPage /></RequireAuth>}
          />
          <Route path="/sealed" element={<RequireAuth><SealedPage /></RequireAuth>} />
          <Route path="/wishlist" element={<RequireAuth><WishlistPage /></RequireAuth>} />
          <Route path="/import-export" element={<RequireAuth><ImportExportPage /></RequireAuth>} />
          <Route path="/settings/profile" element={<RequireAuth><DashboardPage /></RequireAuth>} />
          <Route
            path="/settings/notifications"
            element={<RequireAuth><Placeholder title="Notifications" bolt="bolt 009" /></RequireAuth>}
          />

          {/* Operator. The API is the real guard — this only avoids showing an empty shell. */}
          <Route path="/admin/catalog" element={<RequireAuth><AdminCatalogPage /></RequireAuth>} />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </ErrorBoundary>
    </AppShell>
  );
}
