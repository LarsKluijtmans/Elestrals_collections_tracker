// Single source of runtime config. Everything is a VITE_* env var (see .env.example) — no
// hard-coded URLs or ids anywhere else in the app.
export const env = {
  // The platform publishes login-api on host port 9010 (container 8010). The old :8010 default
  // here reached nothing.
  loginApiUrl: import.meta.env.VITE_LOGIN_API_URL ?? "http://127.0.0.1:9010",
  // The hosted login portal `login()` redirects to — login-web, the same page the platform's
  // own apps use. Setting this is what switches the app from an embedded form to a redirect.
  loginWebUrl: import.meta.env.VITE_LOGIN_WEB_URL ?? "http://127.0.0.1:9090",
  clientId: import.meta.env.VITE_LOGIN_CLIENT_ID ?? "",
  redirectUri: import.meta.env.VITE_REDIRECT_URI ?? `${window.location.origin}/`,
  // Empty string means SAME ORIGIN — requests go to /api/v1/... and nginx proxies them to the
  // backend container, which is the production arrangement. `??` only falls back on
  // null/undefined, so an intentionally empty VITE_BACKEND_URL survives.
  // The dev default is :9500; :9000 is taken by platform-management-api.
  backendUrl: import.meta.env.VITE_BACKEND_URL ?? "http://127.0.0.1:9500",
};
