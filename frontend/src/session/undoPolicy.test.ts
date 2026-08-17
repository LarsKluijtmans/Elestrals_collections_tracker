/**
 * The rule the bolt exists for: undo reverses a delta, not a row — and refuses when it cannot
 * know that it would.
 *
 * Both naive implementations pass a casual reading and fail here, which is why these are pinned:
 *
 *   * "Reverse to the quantity recorded after the add" breaks the moment the same printing is
 *     added twice in one session, which is the normal case emptying a box.
 *   * "Always subtract the delta" corrupts a holding edited in another tab.
 */
import { describe, expect, it } from "vitest";
import { addSessionReducer, initialState } from "./addSessionReducer";
import { holdingKey, type AddRecord, type AddSessionState } from "./types";
import { canUndo, expectedQuantity, refusalMessage } from "./undoPolicy";

function record(overrides: Partial<AddRecord> = {}): AddRecord {
  return {
    id: "r1",
    printingId: "p1",
    condition: "near_mint",
    delta: 1,
    state: "confirmed",
    appliedAt: 0,
    itemId: "item-1",
    label: { name: "Atlas", setCode: "FE01", collectorNumber: "BS1-001", finish: "normal" },
    ...overrides,
  };
}

/** A session that has added the same holding `count` times, all confirmed against one row. */
function sessionWith(count: number, baseline: number, deltas?: number[]): AddSessionState {
  let state = initialState(0);
  for (let n = 0; n < count; n += 1) {
    state = addSessionReducer(state, {
      type: "add/applied",
      record: record({ id: `r${n}`, delta: deltas?.[n] ?? 1, state: "pending", itemId: undefined }),
      baselineQuantity: baseline,
    });
    state = addSessionReducer(state, {
      type: "add/confirmed", recordId: `r${n}`, itemId: "item-1", quantity: baseline + n + 1,
    });
  }
  return state;
}

describe("expectedQuantity", () => {
  it("is the baseline plus every delta this session applied", () => {
    const state = sessionWith(3, 2);
    const holding = state.touched[holdingKey("p1", "near_mint")];
    expect(expectedQuantity(state, holding)).toBe(5);
  });

  it("excludes failed adds, which never reached the server", () => {
    let state = sessionWith(3, 0);
    state = addSessionReducer(state, { type: "add/rejected", recordId: "r1", reason: "offline" });

    const holding = state.touched[holdingKey("p1", "near_mint")];
    expect(expectedQuantity(state, holding)).toBe(2);
  });

  it("includes pending adds, which are on their way", () => {
    // By the time an undo request lands, the server will have applied them. Excluding them would
    // make the expectation too low and every undo during a fast run would be refused.
    let state = sessionWith(1, 0);
    state = addSessionReducer(state, {
      type: "add/applied",
      record: record({ id: "pending-one", state: "pending", itemId: undefined }),
      baselineQuantity: 0,
    });

    const holding = state.touched[holdingKey("p1", "near_mint")];
    expect(expectedQuantity(state, holding)).toBe(2);
  });

  it("excludes an add that was already undone", () => {
    let state = sessionWith(3, 0);
    state = addSessionReducer(state, { type: "undo/applied", recordId: "r2" });

    const holding = state.touched[holdingKey("p1", "near_mint")];
    expect(expectedQuantity(state, holding)).toBe(2);
  });

  it("counts only the holding in question", () => {
    // The same printing in another condition is a different row, and must not inflate this one.
    let state = sessionWith(2, 1);
    state = addSessionReducer(state, {
      type: "add/applied",
      record: record({ id: "other", condition: "damaged", delta: 9 }),
      baselineQuantity: 0,
    });

    const holding = state.touched[holdingKey("p1", "near_mint")];
    expect(expectedQuantity(state, holding)).toBe(3);
  });

  it("sums a mix of positive and negative deltas", () => {
    const state = sessionWith(3, 4, [2, -1, 3]);
    const holding = state.touched[holdingKey("p1", "near_mint")];
    expect(expectedQuantity(state, holding)).toBe(8);
  });
});

describe("canUndo", () => {
  it("undoing one of three adds expects three, not one", () => {
    // **The assertion this file exists for.** "Reverse to what it was before the add" would send
    // an expectation of 1 here, the server would refuse, and undo would appear broken to anybody
    // who added a duplicate — which is everybody.
    const state = sessionWith(3, 0);
    const middle = state.records.find((r) => r.id === "r1")!;

    const verdict = canUndo(state, middle);
    expect(verdict).toEqual({ allowed: true, expectedQuantity: 3, itemId: "item-1" });
  });

  it("allows undoing the most recent add", () => {
    const state = sessionWith(1, 0);
    const verdict = canUndo(state, state.records[0]);
    expect(verdict.allowed).toBe(true);
  });

  it("refuses an add that already went back", () => {
    let state = sessionWith(1, 0);
    state = addSessionReducer(state, { type: "undo/applied", recordId: "r0" });

    const verdict = canUndo(state, state.records[0]);
    expect(verdict).toEqual({
      allowed: false, reason: "That add has already been undone.",
    });
  });

  it("refuses an add that never went through", () => {
    let state = sessionWith(1, 0);
    state = addSessionReducer(state, { type: "add/rejected", recordId: "r0", reason: "offline" });

    const verdict = canUndo(state, state.records[0]);
    expect(verdict.allowed).toBe(false);
    expect((verdict as { reason: string }).reason).toContain("nothing to undo");
  });

  it("refuses while the add is still in flight", () => {
    // There is nothing on the server to reverse yet, and this is refused locally and instantly —
    // no round trip needed to say so.
    let state = initialState(0);
    state = addSessionReducer(state, {
      type: "add/applied",
      record: record({ id: "r0", state: "pending", itemId: undefined }),
      baselineQuantity: 0,
    });

    const verdict = canUndo(state, state.records[0]);
    expect(verdict.allowed).toBe(false);
    expect((verdict as { reason: string }).reason).toContain("Still saving");
  });

  it("refuses a confirmed record that somehow has no row", () => {
    const state = sessionWith(1, 0);
    const orphan = record({ id: "r0", state: "confirmed", itemId: undefined });
    const verdict = canUndo(state, orphan);
    expect(verdict.allowed).toBe(false);
  });

  it("refuses when the session no longer knows the holding", () => {
    const state = initialState(0);
    const verdict = canUndo(state, record());
    expect(verdict).toEqual({
      allowed: false, reason: "This session no longer knows about that holding.",
    });
  });
});

describe("refusalMessage", () => {
  it("says what it expected, what it found, and that nothing changed", () => {
    // "Could not undo" on its own leaves a collector unable to tell whether their collection is
    // now right, which is the state this whole bolt is trying to keep them out of.
    const message = refusalMessage("Atlas (FE01 BS1-001) ×1", 3, 7);
    expect(message).toContain("Atlas (FE01 BS1-001) ×1");
    expect(message).toContain("expected 3");
    expect(message).toContain("found 7");
    expect(message).toContain("Nothing was changed");
  });
});
