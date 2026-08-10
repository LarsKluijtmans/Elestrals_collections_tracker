// Typed client for our FastAPI backend. Every authenticated call carries the signed-in
// user's access token (from react-auth's getAccessToken, which refreshes transparently).
//
// Paths are `/api/v1/*` — see memory-bank/standards/api-conventions.md.
import { env } from "../env";

export type Profile = {
  user_sub: string;
  handle: string | null;
  collection_visibility: "private" | "link" | "public";
  default_currency: string;
  condition_scale: "tcg" | "cardmarket";
  // Platform-owned, read-only here — edited in the platform's own /account.
  email: string | null;
  username: string | null;
  enriched: boolean;
};

export type ProfilePatch = Partial<
  Pick<Profile, "handle" | "collection_visibility" | "default_currency" | "condition_scale">
>;

export type ClientEvent = {
  level?: "debug" | "info" | "warning";
  message: string;
  component?: string;
  context?: Record<string, unknown>;
};

/** The one error shape. `code` is stable and safe to branch on; `message` may change. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type TokenGetter = () => Promise<string | null>;

let tokenGetter: TokenGetter = async () => null;
/** Registered once by the auth layer so modules like ErrorBoundary can report without
 *  threading a token getter through the whole component tree. */
export function registerTokenGetter(getter: TokenGetter): void {
  tokenGetter = getter;
}

async function request(path: string, init?: RequestInit, getToken?: TokenGetter): Promise<Response> {
  const token = await (getToken ?? tokenGetter)();
  const res = await fetch(`${env.backendUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    let code = "error";
    let message = `${init?.method ?? "GET"} ${path} → ${res.status}`;
    let details: Record<string, unknown> = {};
    try {
      const body = await res.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        details = body.error.details ?? {};
      }
    } catch {
      // Non-JSON error body — keep the generic message rather than masking the status.
    }
    throw new ApiError(res.status, code, message, details);
  }
  return res;
}

export async function fetchProfile(getToken?: TokenGetter): Promise<Profile> {
  return (await (await request("/api/v1/me", undefined, getToken)).json()) as Profile;
}

export async function updateProfile(patch: ProfilePatch, getToken?: TokenGetter): Promise<Profile> {
  const res = await request(
    "/api/v1/me",
    { method: "PATCH", body: JSON.stringify(patch) },
    getToken,
  );
  return (await res.json()) as Profile;
}

/**
 * Relay a client event into logging. The browser has no `logs:write` scope and must never
 * reach logs-api directly — the backend stamps the validated caller, so identity cannot be
 * spoofed. Best-effort by design: reporting a problem must not create one.
 */
export async function reportClientEvent(event: ClientEvent): Promise<void> {
  try {
    await request("/api/v1/events", { method: "POST", body: JSON.stringify(event) });
  } catch {
    // Intentionally swallowed.
  }
}
