import { useAuth } from "@lars-kluijtmans/react-auth";
import { Box, Button, CircularProgress, Stack, Typography } from "@mui/material";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { registerTokenGetter } from "../api/backend";
import { authConfig } from "../authConfig";
import { AdminCatalogPage } from "../pages/AdminCatalog";
import { CardDetailPage } from "../pages/CardDetail";
import { DashboardPage } from "../pages/Dashboard";
import {
  AddCardsPage, CollectionPage, ImportExportPage, NotFoundPage,
  Placeholder, SealedPage, WishlistPage,
} from "../pages/Placeholder";
import { ProfilePage } from "../pages/Profile";
import { SetDetailPage } from "../pages/SetDetail";
import { SetsPage } from "../pages/Sets";
import { AppShell } from "./AppShell";
import { ErrorBoundary } from "./ErrorBoundary";
import { PlatformUnavailable } from "./PlatformUnavailable";

/** Where the visitor was heading before we sent them to the login portal. */
const RETURN_TO_KEY = "elestrals.returnTo";

// Auth state decides what renders: a spinner while resolving, the "platform unavailable"
// screen if login-api cannot be reached at all, and otherwise the routed app shell.
//
// The shell renders for ANONYMOUS visitors too. `/sets`, `/sets/:code` and `/cards/:id` are
// public, so the sign-in requirement is scoped to the routes that actually need a session
// rather than hoisted over the whole application.
//
// Sign-in is a REDIRECT to login-web (the hosted portal), matching the platform's own apps.
// Because the browser leaves and returns to a fixed `redirectUri`, the requested path would be
// lost — so it is stashed before the redirect and restored after the code exchange.
export function Gate() {
  const { isAuthenticated, isLoading, getAccessToken } = useAuth();
  const [reachable, setReachable] = useState<boolean | null>(null);
  const navigate = useNavigate();

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

  // Land the callback: the SDK exchanges `?code` itself, leaving the code and state in the URL.
  // Replacing the entry both cleans those query params away and returns the visitor to the page
  // they originally asked for.
  useEffect(() => {
    if (!isAuthenticated) return;
    const params = new URLSearchParams(window.location.search);
    if (!params.has("code") && !params.has("state")) return;

    const back = sessionStorage.getItem(RETURN_TO_KEY);
    sessionStorage.removeItem(RETURN_TO_KEY);
    navigate(back && back !== "/" ? back : "/dashboard", { replace: true });
  }, [isAuthenticated, navigate]);

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
          <Route
            path="/"
            element={<Navigate to={isAuthenticated ? "/dashboard" : "/sets"} replace />}
          />

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
          <Route path="/settings/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
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

/** Gates one route behind a session, redirecting to the hosted login portal if there is none. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <SignInRedirect />;
}

function SignInRedirect() {
  const { t } = useTranslation("app");
  const { login } = useAuth();
  const location = useLocation();
  // StrictMode double-invokes effects in development; without this guard the second run
  // overwrites the stored path and fires a second redirect.
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    sessionStorage.setItem(RETURN_TO_KEY, location.pathname + location.search);
    void login();
  }, [login, location.pathname, location.search]);

  // Shown only for the moment before the browser leaves — and permanently if the redirect is
  // blocked, which is why the manual link is here rather than a bare spinner.
  return (
    <Box sx={{ display: "grid", placeItems: "center", minHeight: "60vh", p: 4 }}>
      <Stack sx={{ gap: 2, alignItems: "center", textAlign: "center" }}>
        <CircularProgress size={22} />
        <Typography sx={{ fontSize: 14 }}>{t("auth.redirecting")}</Typography>
        <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
          {t("auth.manual")}
        </Typography>
        <Button variant="outlined" size="small" onClick={() => void login()}>
          {t("auth.continueToSignIn")}
        </Button>
      </Stack>
    </Box>
  );
}
