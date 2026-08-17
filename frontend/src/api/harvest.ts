// Typed client for harvest-api — the second backend (intent 002).
//
// A separate module from `backend.ts` because it is a separate service with a separate base URL,
// a separate scope and a separate availability story. Folding it into the same client would
// make it look like one API with some admin routes, which is exactly the impression FR-13 is
// arranged to prevent: harvest-api can be down, blocked or mid-rewrite while the collection
// tracker is perfectly fine.
//
// Every route here requires `elestrals:admin`. There are no public harvest routes.
import { env } from "../env";
import { ApiError } from "./backend";

export type SourceHealth = {
  key: string;
  name: string;
  access_mode: "official_api" | "feed" | "scrape" | "unknown";
  enabled: boolean;
  reports_sold: boolean;
  rate_limit_per_min: number;
  /** Shown next to the source's name. ADR-004 accepts a risk per source; the note and the
   *  person who accepted it belong where an admin sees them, not filed somewhere else. */
  tos_review_note: string | null;
  risk_accepted_by: string | null;
  risk_accepted_on: string | null;
  quarantined: boolean;
  quarantined_until: string | null;
  quarantine_reason: string | null;
  quarantine_level: number;
  last_deep_run: RunSummary | null;
  last_light_run: RunSummary | null;
  accept_rate_deep: [string, number][];
  accept_rate_light: [string, number][];
  live_listings: number;
  /** Distinct from "ran and found nothing", and the UI must not render them the same. */
  never_run: boolean;
};

export type RunSummary = {
  id: string;
  source_key: string;
  mode: "deep" | "light";
  status: "running" | "success" | "partial" | "failed";
  triggered_by: string;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  queries: number;
  fetched: number;
  parsed: number;
  accepted: number;
  rejected: number;
  discovered: number;
  ended: number;
  error_summary: string | null;
  stop_requested: boolean;
};

export type ListingSummary = {
  id: string;
  source_key: string;
  external_id: string;
  title: string;
  url: string;
  image_url: string | null;
  kind: "single" | "sealed" | "lot" | "unknown";
  /** Four values, and `ended_unknown` must never be rendered as "sold" — see `statusLabel`. */
  status: "active" | "ended_sold" | "ended_unsold" | "ended_unknown";
  price_cents: number;
  currency: string;
  shipping_cents: number | null;
  quantity: number;
  buying_format: string;
  location_country: string | null;
  printing_id: string | null;
  sealed_product_id: string | null;
  condition: string | null;
  match_confidence: number | null;
  match_note: string | null;
  product_label: string | null;
  first_seen_at: string;
  last_seen_at: string;
  ended_at: string | null;
  sold_price_cents: number | null;
};

export type ListingFilters = {
  source?: string;
  run_id?: string;
  status?: string;
  kind?: string;
  matched?: boolean;
  min_confidence?: number;
  max_confidence?: number;
  search?: string;
  limit?: number;
  offset?: number;
};

export type RollupRun = {
  since: string;
  since_days: number;
  /** Days that actually carried observations — not the window's length. Asking for a week and
   *  being told 2 is a true statement about coverage, and worth showing as one. */
  days: number;
  rows: number;
  excluded: number;
  max_since_days: number;
};

export type SweepResult = { swept: number; stale_after_minutes: number };

export type CoverageReport = {
  tracked_printings: number;
  priced_printings: number;
  window_days: number;
  match_quality: { source_key: string; mode: string; points: [string, number][] }[];
  top_rejections: { reason: string; count: number }[];
  unmatched_no_catalog: number;
  unmatched_under_floor: number;
};

export type DistributionReport = {
  printing_id: string | null;
  sealed_product_id: string | null;
  product_label: string | null;
  day: string | null;
  points: {
    id: number;
    source_key: string;
    sale_type: "sold" | "listed";
    observed_at: string;
    price_cents: number;
    currency: string;
    condition: string | null;
    is_outlier: boolean;
    source_url: string;
  }[];
  agreement: {
    source_key: string;
    median_cents: number;
    observation_count: number;
    delta_pct: number;
  }[];
  single_source: boolean;
};

/**
 * The one place `ended_unknown` is turned into words.
 *
 * A listing that vanished from a source that lists only active offers may have sold, expired,
 * been cancelled, been relisted, or been hidden from our region — and only one of those is a
 * sale. The whole invariant chain from the connector through the runner to the fact table can be
 * undone here by one loose label, so it is not left to each component to phrase.
 */
export function statusLabel(status: ListingSummary["status"]): string {
  switch (status) {
    case "active":
      return "Live";
    case "ended_sold":
      return "Sold";
    case "ended_unsold":
      return "Ended, unsold";
    case "ended_unknown":
      return "Ended, reason unknown";
  }
}

type TokenGetter = () => Promise<string | null>;

async function harvestRequest(
  path: string,
  getToken: TokenGetter,
  init?: RequestInit,
): Promise<Response> {
  const token = await getToken();
  const res = await fetch(`${env.harvestUrl}${path}`, {
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
      // Non-JSON error body — keep the status rather than masking it. A harvest-api that is
      // down answers with nginx HTML, and "502" is more useful than "unexpected token <".
    }
    throw new ApiError(res.status, code, message, details);
  }
  return res;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    search.append(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export const harvestApi = {
  async health(getToken: TokenGetter) {
    const res = await harvestRequest("/api/v1/health", getToken);
    return res.json();
  },

  async sources(getToken: TokenGetter): Promise<SourceHealth[]> {
    const res = await harvestRequest("/api/v1/admin/sources", getToken);
    return res.json();
  },

  async disableSource(getToken: TokenGetter, key: string): Promise<SourceHealth> {
    const res = await harvestRequest(`/api/v1/admin/sources/${key}/disable`, getToken, {
      method: "POST",
    });
    return res.json();
  },

  async clearQuarantine(getToken: TokenGetter, key: string): Promise<SourceHealth> {
    const res = await harvestRequest(
      `/api/v1/admin/sources/${key}/clear-quarantine`,
      getToken,
      { method: "POST" },
    );
    return res.json();
  },

  /** Returns immediately with a run id — a deep scan is a four-hour job, not an HTTP request. */
  async triggerScan(
    getToken: TokenGetter,
    key: string,
    mode: "deep" | "light",
  ): Promise<{ run_id: string; status: string }> {
    const res = await harvestRequest(`/api/v1/admin/sources/${key}/scan/${mode}`, getToken, {
      method: "POST",
    });
    return res.json();
  },

  async stopRun(getToken: TokenGetter, runId: string): Promise<RunSummary> {
    const res = await harvestRequest(`/api/v1/admin/runs/${runId}/stop`, getToken, {
      method: "POST",
    });
    return res.json();
  },

  async runs(
    getToken: TokenGetter,
    params: { source?: string; mode?: string; status?: string; limit?: number } = {},
  ): Promise<{ items: RunSummary[]; total: number }> {
    const res = await harvestRequest(`/api/v1/admin/runs${qs(params)}`, getToken);
    return res.json();
  },

  /** Polled while a scan runs. The run row is the source of truth, so a poll that lands after
   *  the scan finished returns the final status rather than missing an event. */
  async run(getToken: TokenGetter, runId: string): Promise<RunSummary> {
    const res = await harvestRequest(`/api/v1/admin/runs/${runId}`, getToken);
    return res.json();
  },

  async listings(
    getToken: TokenGetter,
    filters: ListingFilters = {},
  ): Promise<{ items: ListingSummary[]; total: number }> {
    const res = await harvestRequest(`/api/v1/admin/listings${qs(filters)}`, getToken);
    return res.json();
  },

  async coverage(getToken: TokenGetter, windowDays = 7): Promise<CoverageReport> {
    const res = await harvestRequest(
      `/api/v1/admin/analysis/coverage${qs({ window_days: windowDays })}`,
      getToken,
    );
    return res.json();
  },

  async distribution(
    getToken: TokenGetter,
    params: { printing_id?: string; sealed_product_id?: string; day?: string },
  ): Promise<DistributionReport> {
    const res = await harvestRequest(
      `/api/v1/admin/analysis/distribution${qs(params)}`,
      getToken,
    );
    return res.json();
  },

  /**
   * Recompute `price_daily` now, rather than at the next beat.
   *
   * Unlike a scan this is synchronous, because a rollup over recent days is seconds and an admin
   * who pressed "recompute" wants the numbers rather than a task id. The window is capped
   * server-side; a full-history rebuild is `python -m app.harvest --rollup`.
   */
  async recomputeRollup(getToken: TokenGetter, sinceDays = 7): Promise<RollupRun> {
    const res = await harvestRequest(
      `/api/v1/admin/maintenance/rollup${qs({ since_days: sinceDays })}`,
      getToken,
      { method: "POST" },
    );
    return res.json();
  },

  /** Fail runs orphaned by a deploy, so the duplicate-run check stops refusing a manual scan. */
  async sweepStaleRuns(getToken: TokenGetter): Promise<SweepResult> {
    const res = await harvestRequest("/api/v1/admin/maintenance/sweep", getToken, {
      method: "POST",
    });
    return res.json();
  },
};
