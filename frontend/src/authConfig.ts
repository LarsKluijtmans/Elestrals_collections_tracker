import type { AuthProviderConfig } from "@lars-kluijtmans/react-auth";
import { env } from "./env";

// Embedded login: we deliberately DON'T set `hostedLoginUrl`. <LoginForm> renders the login UI
// in-app and completes the session via useAuth().completeLogin — no redirect to a portal.
// Tokens are kept in memory by default (cleared on reload, safest against XSS).
export const authConfig: AuthProviderConfig = {
  authApiUrl: env.loginApiUrl,
  clientId: env.clientId,
  redirectUri: env.redirectUri,
  scope: "openid profile email",
};
