// Price surfaces on elestrals-api — rollups only.
//
// These read `price_daily` through a cross-schema grant, which is the entire contract between
// the two services. No raw listing, match note or rejection reason is reachable from here; that
// material is admin-only and lives behind `harvest.ts`.
import { env } from "../env";
import { ApiError } from "./backend";

export type PricePoint = {
  day: string;
  low_cents: number;
  median_cents: number;
  high_cents: number;
  currency: string;
  /** Both present on every point. A median from two sales and one from two hundred are the
   *  same number and mean very different things. */
  observation_count: number;
  confidence: "low" | "medium" | "high";
};

export type PriceHistory = {
  printing_id: string;
  sale_type: "sold" | "listed";
  condition: string | null;
  points: PricePoint[];
  /** Present and empty rather than absent, so the client renders "no observations yet" instead
   *  of a flat line at zero. */
  is_empty: boolean;
  priced_as_of: string | null;
  /** harvest-api being down degrades freshness, never availability — so a stale rollup is
   *  labelled and served rather than withheld. */
  is_stale: boolean;
};

export type Mover = {
  printing_id: string;
  from_cents: number;
  to_cents: number;
  change_pct: number;
};

export type MarketOverview = {
  movers_up: Mover[];
  movers_down: Mover[];
  window_days: number;
  min_observations: number;
  priced_as_of: string | null;
};

export type Portfolio = {
  total_cents: number;
  currency: string;
  valued_items: number;
  /** Excluded and counted, never folded into the total as zero. */
  unvalued_items: number;
  unvalued_reasons: Record<string, number>;
  coverage: number;
  confidence: "low" | "medium" | "high";
  priced_as_of: string | null;
  unvalued_item_ids: string[];
};

type TokenGetter = () => Promise<string | null>;

async function get(path: string, getToken?: TokenGetter): Promise<Response> {
  const token = getToken ? await getToken() : null;
  const res = await fetch(`${env.backendUrl}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    let code = "error";
    let message = `GET ${path} → ${res.status}`;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {
      // Keep the status.
    }
    throw new ApiError(res.status, code, message);
  }
  return res;
}

export type HistoryPoint = {
  day: string;
  item_count: number;
  distinct_printings: number;
  /** `null` means not valued. The chart **breaks** here — it does not draw a zero or interpolate. */
  total_value_cents: number | null;
  currency: string;
  confidence: string;
};

export type Performer = {
  printing_id: string;
  name: string;
  set_code: string;
  contribution_cents: number;
  unit_cents: number;
  quantity: number;
};

export type PortfolioHistory = {
  points: HistoryPoint[];
  prices_start_on: string | null;
  profit_and_loss: {
    cost_cents: number;
    market_cents: number;
    gain_cents: number;
    covered_items: number;
    uncovered_items: number;
    coverage: number;
  } | null;
  best: Performer[];
  worst: Performer[];
};

export type PriceAlert = {
  id: string;
  printing_id: string;
  card_id: string;
  name: string;
  set_code: string;
  direction: string;
  threshold_cents: number;
  currency: string;
  is_active: boolean;
  last_fired_at: string | null;
  cooldown_until: string | null;
  created_at: string;
};

export const pricesApi = {
  /** Public — the price tab does not vary on the caller and is cacheable. */
  async history(
    printingId: string,
    params: { range?: string; sale_type?: string; condition?: string } = {},
  ): Promise<PriceHistory> {
    const search = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) search.append(k, v);
    const query = search.toString();
    const res = await get(`/api/v1/prices/printings/${printingId}${query ? `?${query}` : ""}`);
    return res.json();
  },

  /** Public. */
  async overview(windowDays = 7): Promise<MarketOverview> {
    const res = await get(`/api/v1/prices/overview?window_days=${windowDays}`);
    return res.json();
  },

  /** Signed in, and scoped to the caller by the token — never by a parameter. */
  async portfolioHistory(
    getToken: TokenGetter, days = 365, currency = "EUR",
  ): Promise<PortfolioHistory> {
    const res = await get(
      `/api/v1/portfolio/history?days=${days}&currency=${currency}`, getToken,
    );
    return res.json();
  },

  async alerts(getToken: TokenGetter): Promise<PriceAlert[]> {
    const res = await get("/api/v1/alerts", getToken);
    return res.json();
  },

  async portfolio(getToken: TokenGetter, currency = "EUR"): Promise<Portfolio> {
    const res = await get(`/api/v1/portfolio?currency=${currency}`, getToken);
    return res.json();
  },
};
