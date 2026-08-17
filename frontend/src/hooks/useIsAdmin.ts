import { useAuth } from "@lars-kluijtmans/react-auth";
import { useEffect, useState } from "react";

/** The scope harvest-api requires on every one of its routes. */
export const ADMIN_SCOPE = "elestrals:admin";

/**
 * Whether the signed-in user holds `elestrals:admin`.
 *
 * **This is a rendering decision, not an authorisation decision.** The authorisation happens in
 * harvest-api, in one dependency every admin route carries; a caller without the scope gets a
 * `403` whatever this hook says. What it is for is deciding not to *download* the admin bundle:
 * hiding an admin section client-side leaves the code and every endpoint path it calls in the
 * bundle for anyone who opens a network tab.
 *
 * The scope is read out of the access token's `scope` claim — the same claim the two backends
 * check. Decoding the payload is not verification and is not treated as any; the token was
 * issued to this browser and its signature is checked server-side on every call.
 */
export function useIsAdmin(): { isAdmin: boolean; isResolved: boolean } {
  const { isAuthenticated, isLoading, getAccessToken } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);
  const [isResolved, setIsResolved] = useState(false);

  useEffect(() => {
    let active = true;
    if (isLoading) return;
    if (!isAuthenticated) {
      setIsAdmin(false);
      setIsResolved(true);
      return;
    }
    getAccessToken()
      .then((token) => {
        if (!active) return;
        setIsAdmin(scopesOf(token).includes(ADMIN_SCOPE));
        setIsResolved(true);
      })
      .catch(() => {
        if (!active) return;
        // Fail closed. A token we cannot read is not a token that grants anything.
        setIsAdmin(false);
        setIsResolved(true);
      });
    return () => {
      active = false;
    };
  }, [isAuthenticated, isLoading, getAccessToken]);

  return { isAdmin, isResolved };
}

function scopesOf(token: string | null): string[] {
  if (!token) return [];
  try {
    const [, payload] = token.split(".");
    if (!payload) return [];
    const json = JSON.parse(
      decodeURIComponent(
        atob(payload.replace(/-/g, "+").replace(/_/g, "/"))
          .split("")
          .map((c) => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`)
          .join(""),
      ),
    );
    return typeof json.scope === "string" ? json.scope.split(" ") : [];
  } catch {
    return [];
  }
}
