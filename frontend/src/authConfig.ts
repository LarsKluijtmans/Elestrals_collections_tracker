import type { AuthProviderConfig } from "@lars-kluijtmans/react-auth";
import { env } from "./env";

// Hosted login: `login()` redirects the browser to login-web, exactly as the platform's own
// apps do. Tokens are kept in memory by default (cleared on reload, safest against XSS).
//
// The trade-off this makes, stated plainly: the embedded <LoginForm> never changed the URL, so
// a deep link survived sign-in for free. A redirect leaves the app and comes back to
// `redirectUri`, which would drop the path the visitor actually asked for — so `Gate` now
// stores it before redirecting and restores it after the code exchange. That is the
// return-path plumbing the embedded flow avoided; it is the cost of the hosted portal.
export const authConfig: AuthProviderConfig = {
  authApiUrl: env.loginApiUrl,
  hostedLoginUrl: env.loginWebUrl,
  clientId: env.clientId,
  redirectUri: env.redirectUri,
  scope: "openid profile email",
};
