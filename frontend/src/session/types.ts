// The add session's vocabulary — stage 1's domain model, in types.
//
// Everything here lives in memory for the length of a session and is gone when the tab closes.
// That is deliberate: a session is the condition you have selected, the tally you are watching
// and the twenty adds you might take back. Persisting it would turn "close the tab" into a
// state-management problem for no user-visible gain, and story 018 already says the stack is
// session-scoped and states so in the UI.

export type Condition =
  | "mint" | "near_mint" | "lightly_played" | "moderately_played" | "heavily_played" | "damaged";

export type AddState = "pending" | "confirmed" | "failed" | "undone";

/** Captured at add time so a failure message can name the card without a fetch that may also
 *  fail. "Could not add that one" is not a failure message. */
export type CardLabel = {
  name: string;
  setCode: string;
  collectorNumber: string;
  finish: string;
};

/** Condition, finish, language and edition, carried from one add to the next.
 *
 *  The single largest contributor to the five-second target: a collector emptying a uniform box
 *  should set these once. Immutable — changing one replaces the object. */
export type CarriedDefaults = {
  condition: Condition;
  finish: string;
  language: string;
  edition: string;
};

/** One act of adding. **The unit of undo** — not a row, not a card.
 *
 *  `delta` may be negative (a grid shift-click) and may be greater than one (a coalesced burst).
 *  Three clicks in 300ms is one record of +3, not three of +1; anything else makes the undo stack
 *  a keystroke log. */
export type AddRecord = {
  id: string;
  printingId: string;
  condition: Condition;
  delta: number;
  state: AddState;
  appliedAt: number;
  label: CardLabel;
  /** Set once the server confirms, so undo knows which row to adjust. */
  itemId?: string;
  /** Why it failed, or why an undo was refused. Shown, never swallowed. */
  reason?: string;
};

/** Everything this session has done to one holding, and what it looked like before.
 *
 *  `baselineQuantity` is the whole reason undo can tell "changed by my own three adds" (fine)
 *  from "changed by somebody else" (refuse) — see `undoPolicy`. */
export type TouchedHolding = {
  key: string;
  printingId: string;
  condition: Condition;
  baselineQuantity: number;
  itemId?: string;
};

export type AddSessionState = {
  carried: CarriedDefaults;
  records: AddRecord[];
  touched: Record<string, TouchedHolding>;
  /** The last announcement, for the live region. Failures are assertive; everything else polite.
   *
   *  `seq` increments on every announcement and is what makes two *identical* messages in a row
   *  distinguishable — see `LiveAnnouncer`, which alternates regions on its parity. It is a
   *  counter rather than a timestamp deliberately: `Date.now()` has millisecond resolution, two
   *  adds can land inside one millisecond, and "usually different" is not a guarantee. */
  announcement: { message: string; assertive: boolean; seq: number } | null;
  startedAt: number;
};

/** The undo stack is capped, and **the cap is visible in the UI** — so "why can I not undo that
 *  one" has an answer on screen rather than in a comment. */
export const UNDO_LIMIT = 20;

export const DEFAULT_CARRIED: CarriedDefaults = {
  condition: "near_mint",
  finish: "normal",
  language: "en",
  edition: "unlimited",
};

/** A holding is identified by printing **and condition**: the same card in two conditions is two
 *  holdings, and merging them would make undo reverse the wrong one. */
export function holdingKey(printingId: string, condition: Condition): string {
  return `${printingId}:${condition}`;
}

export type AddSessionAction =
  | { type: "add/applied"; record: AddRecord; baselineQuantity: number }
  | { type: "add/confirmed"; recordId: string; itemId: string; quantity: number }
  | { type: "add/rejected"; recordId: string; reason: string }
  | { type: "undo/applied"; recordId: string }
  | { type: "undo/refused"; recordId: string; expected: number; actual: number }
  | { type: "defaults/changed"; patch: Partial<CarriedDefaults> }
  | { type: "session/reset" };
