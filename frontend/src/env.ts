// Single source of runtime config. Everything is a VITE_* env var (see .env.example) — no
// hard-coded URLs or ids anywhere else in the app.
export const env = {
  loginApiUrl: import.meta.env.VITE_LOGIN_API_URL ?? "http://127.0.0.1:8010",
  clientId: import.meta.env.VITE_LOGIN_CLIENT_ID ?? "",
  redirectUri: import.meta.env.VITE_REDIRECT_URI ?? `${window.location.origin}/`,
  backendUrl: import.meta.env.VITE_BACKEND_URL ?? "http://127.0.0.1:9000",
};
