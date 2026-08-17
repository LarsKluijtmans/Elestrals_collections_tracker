// The rule this bolt exists for.
//
//   Undo reverses a delta, not a row — and refuses when it cannot know that it would.
//
// Both naive implementations fail, and it is worth writing down why, because both look correct:
//
//   * "Reverse to the quantity recorded after the add" breaks the moment the same printing is
//     added again in the same session — which is the normal case emptying a box.
//   * "Always subtract the delta" silently corrupts a holding that was edited in another tab,
//     and story 018 explicitly requires a refusal rather than a guess.
//
// So the session keeps what a holding looked like **before it first touched it**, plus every
// delta it has applied since. That is enough to compute what the quantity should be, and
// therefore enough to tell "changed by my own adds" from "changed by somebody else" — using only
// state the session already has. No version column, no extra round trip, no guessing.
//
// The server re-checks the same thing atomically (ADR-005). Neither layer is redundant: this one
// gives an instant, explained refusal without a round trip; that one is what actually holds under
// concurrency.
import { holdingKey, type AddRecord, type AddSessionState, type TouchedHolding } from "./types";

export type UndoVerdict =
  | { allowed: true; expectedQuantity: number; itemId: string }
  | { allowed: false; reason: string };

/**
 * What the quantity of a holding *should* be, if only this session has touched it.
 *
 *     expected = baseline + sum(delta of every non-undone record on this holding)
 *
 * Failed records are excluded because they never reached the server. Pending ones are included
 * because they are on their way and the server will have applied them by the time an undo lands.
 */
export function expectedQuantity(state: AddSessionState, holding: TouchedHolding): number {
  return state.records
    .filter(
      (record) =>
        holdingKey(record.printingId, record.condition) === holding.key &&
        record.state !== "undone" &&
        record.state !== "failed",
    )
    .reduce((total, record) => total + record.delta, holding.baselineQuantity);
}

export function canUndo(state: AddSessionState, record: AddRecord): UndoVerdict {
  if (record.state === "undone") {
    return { allowed: false, reason: "That add has already been undone." };
  }
  if (record.state === "failed") {
    return { allowed: false, reason: "That add never went through, so there is nothing to undo." };
  }
  if (record.state === "pending" || !record.itemId) {
    // Nothing on the server yet to reverse. The control is disabled rather than hidden, so the
    // list does not shift under the cursor while a request is in flight.
    return { allowed: false, reason: "Still saving — try again in a moment." };
  }

  const holding = state.touched[holdingKey(record.printingId, record.condition)];
  if (!holding) {
    return { allowed: false, reason: "This session no longer knows about that holding." };
  }

  return {
    allowed: true,
    expectedQuantity: expectedQuantity(state, holding),
    itemId: record.itemId,
  };
}

/** The message shown when the server refuses — it changed under us.
 *
 *  Says what was expected and what was found, because "could not undo" leaves the collector with
 *  no idea whether their collection is now right. */
export function refusalMessage(label: string, expected: number, actual: number): string {
  return (
    `Could not undo ${label}: it changed since you added it ` +
    `(expected ${expected}, found ${actual}). Nothing was changed.`
  );
}
