// Phase-1 route table. Mirrors the page inventory in memory-bank/standards/ux-guide.md §11.
// Routes marked `phase` > 1 are not mounted yet — they are listed so the shell's navigation
// and the plan cannot drift apart silently.
import type { ReactNode } from "react";

export type RouteDef = {
  path: string;
  label: string;
  /** 'public' | 'user' | 'operator' */
  auth: "public" | "user" | "operator";
  phase: 1 | 2 | 3;
  /** Shown in the left rail. */
  inNav: boolean;
  element?: ReactNode;
};

export const ROUTES: RouteDef[] = [
  { path: "/dashboard", label: "Dashboard", auth: "user", phase: 1, inNav: true },
  { path: "/collection", label: "Collection", auth: "user", phase: 1, inNav: true },
  { path: "/collection/add", label: "Add cards", auth: "user", phase: 1, inNav: false },
  { path: "/collection/add/set/:setCode", label: "Add from set", auth: "user", phase: 1, inNav: false },
  { path: "/sets", label: "Sets", auth: "public", phase: 1, inNav: true },
  { path: "/sets/:code", label: "Set", auth: "public", phase: 1, inNav: false },
  { path: "/cards/:id", label: "Card", auth: "public", phase: 1, inNav: false },
  { path: "/sealed", label: "Sealed", auth: "user", phase: 1, inNav: true },
  { path: "/wishlist", label: "Wishlist", auth: "user", phase: 1, inNav: true },
  { path: "/import-export", label: "Import / export", auth: "user", phase: 1, inNav: true },
  { path: "/settings/profile", label: "Settings", auth: "user", phase: 1, inNav: true },
  { path: "/settings/notifications", label: "Notifications", auth: "user", phase: 1, inNav: false },
  { path: "/u/:handle", label: "Public collection", auth: "public", phase: 1, inNav: false },
  { path: "/admin/catalog", label: "Catalog", auth: "operator", phase: 1, inNav: false },

  // Phase 2 — not mounted yet.
  { path: "/prices", label: "Prices", auth: "public", phase: 2, inNav: false },
  { path: "/portfolio", label: "Portfolio", auth: "user", phase: 2, inNav: false },
  { path: "/alerts", label: "Alerts", auth: "user", phase: 2, inNav: false },
  { path: "/admin/scrapers", label: "Scrapers", auth: "operator", phase: 2, inNav: false },

  // Phase 3 — not mounted yet.
  { path: "/market", label: "Market", auth: "public", phase: 3, inNav: false },
  { path: "/sell", label: "Selling", auth: "user", phase: 3, inNav: false },
  { path: "/orders", label: "Orders", auth: "user", phase: 3, inNav: false },
  { path: "/messages", label: "Messages", auth: "user", phase: 3, inNav: false },
];

export const NAV_ROUTES = ROUTES.filter((r) => r.inNav && r.phase === 1);
