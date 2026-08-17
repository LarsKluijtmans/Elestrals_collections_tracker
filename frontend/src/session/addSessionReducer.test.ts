/**
 * The add session's state transitions — stage 1's rules, with no DOM in sight.
 *
 * These are the assertions that decide whether a collector's data is right. If one of them needed
 * a component rendered to express, the rule would be in the wrong layer.
 */
import { describe, expect, it } from "vitest";
import {
  addSessionReducer,
  describe as describeRecord,
  initialState,
  lastUndoable,
  recentAdds,
  tally,
} from "./addSessionReducer";
import {
  DEFAULT_CARRIED,
  holdingKey,
  UNDO_LIMIT,
  type AddRecord,
  type AddSessionState,
  type Condition,
} from "./types";

function record(overrides: Partial<AddRecord> = {}): AddRecord {
  return {
    id: overrides.id ?? `r-${Math.random().toString(36).slice(2)}`,
    printingId: "p1",
    condition: "near_mint",
    delta: 1,
    state: "pending",
    appliedAt: 0,
    label: { name: "Atlas", setCode: "FE01", collectorNumber: "BS1-001", finish: "normal" },
    ...overrides,
  };
}

/** Apply a sequence of adds, each with the baseline the session would have captured. */
function applyAdds(
  state: AddSessionState,
  entries: Array<{ record: AddRecord; baselineQuantity?: number }>,
): AddSessionState {
  return entries.reduce(
    (acc, entry) =>
      addSessionReducer(acc, {
        type: "add/applied",
        record: entry.record,
        baselineQuantity: entry.baselineQuantity ?? 0,
      }),
    state,
  );
}

describe("add/applied", () => {
  it("moves the tally before any response", () => {
    // The whole product thesis: the network never gates the next keystroke.
    const state = applyAdds(initialState(0), [{ record: record({ delta: 2 }) }]);
    expect(tally(state)).toEqual({ adds: 1, quantity: 2 });
    expect(state.records[0].state).toBe("pending");
  });

  it("records a holding's baseline only on first touch", () => {
    // The bug this prevents: if a later add overwrote the baseline, it would come to mean
    // "before the most recent add", and `expectedQuantity` would double-count every earlier
    // delta — so undo would compute a number the server never held and refuse every time.
    const first = record({ id: "a" });
    const second = record({ id: "b" });

    let state = applyAdds(initialState(0), [{ record: first, baselineQuantity: 4 }]);
    state = applyAdds(state, [{ record: second, baselineQuantity: 5 }]);

    expect(state.touched[holdingKey("p1", "near_mint")].baselineQuantity).toBe(4);
  });

  it("treats the same printing in two conditions as two holdings", () => {
    // Merging them would make undo reverse the wrong one.
    let state = applyAdds(initialState(0), [
      { record: record({ id: "a", condition: "near_mint" }), baselineQuantity: 1 },
    ]);
    state = applyAdds(state, [
      { record: record({ id: "b", condition: "damaged" as Condition }), baselineQuantity: 7 },
    ]);

    expect(Object.keys(state.touched)).toHaveLength(2);
    expect(state.touched[holdingKey("p1", "damaged" as Condition)].baselineQuantity).toBe(7);
  });

  it("announces politely, naming the card", () => {
    const state = applyAdds(initialState(0), [{ record: record({ delta: 3 }) }]);
    expect(state.announcement?.assertive).toBe(false);
    expect(state.announcement?.message).toBe("Added Atlas (FE01 BS1-001) ×3");
  });

  it("makes two identical adds in a row distinguishable", () => {
    // A collector emptying a box of duplicates hits this immediately, and `LiveAnnouncer` needs
    // the two to differ or the second add is silent to a screen reader. `Date.now()` was the
    // original mechanism and this test is why it is not: both adds land in the same millisecond.
    const first = applyAdds(initialState(0), [{ record: record({ id: "a" }) }]);
    const second = applyAdds(first, [{ record: record({ id: "b" }) }]);

    expect(second.announcement?.message).toBe(first.announcement?.message);
    expect(second.announcement?.seq).toBe((first.announcement?.seq ?? 0) + 1);
  });

  it("increments the sequence strictly, whatever the transition", () => {
    let state = applyAdds(initialState(0), [{ record: record({ id: "a" }) }]);
    const seen = [state.announcement!.seq];

    state = addSessionReducer(state, { type: "add/rejected", recordId: "a", reason: "offline" });
    seen.push(state.announcement!.seq);
    state = addSessionReducer(state, { type: "defaults/changed", patch: { finish: "foil" } });
    seen.push(state.announcement!.seq);

    expect(seen).toEqual([1, 2, 3]);
  });
});

describe("the undo stack", () => {
  it("keeps the newest and ages out the oldest at the cap", () => {
    // FIFO eviction, not refusal. The most recent add must always be undoable.
    let state = initialState(0);
    for (let n = 0; n < UNDO_LIMIT + 5; n += 1) {
      state = applyAdds(state, [{ record: record({ id: `r${n}` }) }]);
    }

    expect(state.records).toHaveLength(UNDO_LIMIT);
    expect(state.records[0].id).toBe(`r${UNDO_LIMIT + 4}`);
    expect(state.records.some((r) => r.id === "r0")).toBe(false);
  });

  it("shows the five most recent, newest first", () => {
    let state = initialState(0);
    for (let n = 0; n < 8; n += 1) {
      state = applyAdds(state, [{ record: record({ id: `r${n}` }) }]);
    }
    expect(recentAdds(state).map((r) => r.id)).toEqual(["r7", "r6", "r5", "r4", "r3"]);
  });

  it("offers only a confirmed add to Ctrl+Z", () => {
    // A pending add has nothing on the server to reverse yet.
    let state = applyAdds(initialState(0), [{ record: record({ id: "a" }) }]);
    expect(lastUndoable(state)).toBeNull();

    state = addSessionReducer(state, { type: "add/confirmed", recordId: "a", itemId: "i1", quantity: 1 });
    expect(lastUndoable(state)?.id).toBe("a");
  });
});

describe("add/confirmed", () => {
  it("stamps the item id on the record and on the holding", () => {
    // The holding needs it too: undo of a *later* add on the same holding has to know the row.
    let state = applyAdds(initialState(0), [{ record: record({ id: "a" }) }]);
    state = addSessionReducer(state, {
      type: "add/confirmed", recordId: "a", itemId: "item-1", quantity: 1,
    });

    expect(state.records[0].state).toBe("confirmed");
    expect(state.records[0].itemId).toBe("item-1");
    expect(state.touched[holdingKey("p1", "near_mint")].itemId).toBe("item-1");
  });

  it("does not re-announce", () => {
    // Confirmation is not news. Announcing it would interrupt a fast run of adds with noise.
    let state = applyAdds(initialState(0), [{ record: record({ id: "a" }) }]);
    const announced = state.announcement;
    state = addSessionReducer(state, {
      type: "add/confirmed", recordId: "a", itemId: "i", quantity: 1,
    });
    expect(state.announcement).toBe(announced);
  });
});

describe("add/rejected", () => {
  it("reverts the tally", () => {
    let state = applyAdds(initialState(0), [{ record: record({ id: "a", delta: 2 }) }]);
    state = addSessionReducer(state, { type: "add/rejected", recordId: "a", reason: "offline" });

    expect(tally(state)).toEqual({ adds: 0, quantity: 0 });
  });

  it("says so assertively and names the card", () => {
    // Silence is the one unacceptable outcome: a collector who does not notice a failed add has
    // a wrong collection and no way to find out.
    let state = applyAdds(initialState(0), [{ record: record({ id: "a" }) }]);
    state = addSessionReducer(state, { type: "add/rejected", recordId: "a", reason: "offline" });

    expect(state.announcement?.assertive).toBe(true);
    expect(state.announcement?.message).toContain("Atlas (FE01 BS1-001)");
    expect(state.announcement?.message).toContain("offline");
    expect(state.records[0].reason).toBe("offline");
  });
});

describe("undo", () => {
  it("marks the record undone and drops it from the tally", () => {
    let state = applyAdds(initialState(0), [{ record: record({ id: "a", delta: 2 }) }]);
    state = addSessionReducer(state, { type: "undo/applied", recordId: "a" });

    expect(state.records[0].state).toBe("undone");
    expect(tally(state)).toEqual({ adds: 0, quantity: 0 });
    expect(state.announcement?.message).toBe("Undid Atlas (FE01 BS1-001) ×2");
  });

  it("a refusal states both numbers and changes nothing", () => {
    let state = applyAdds(initialState(0), [{ record: record({ id: "a" }) }]);
    state = addSessionReducer(state, {
      type: "add/confirmed", recordId: "a", itemId: "i", quantity: 1,
    });
    state = addSessionReducer(state, {
      type: "undo/refused", recordId: "a", expected: 1, actual: 5,
    });

    expect(state.records[0].state).toBe("confirmed");
    expect(state.records[0].reason).toContain("expected 1, found 5");
    expect(state.records[0].reason).toContain("Nothing was changed");
    expect(state.announcement?.assertive).toBe(true);
    // Still counted — the add is still there, which is the point of refusing.
    expect(tally(state)).toEqual({ adds: 1, quantity: 1 });
  });
});

describe("carried defaults", () => {
  it("start at near mint and normal", () => {
    expect(initialState(0).carried).toEqual(DEFAULT_CARRIED);
  });

  it("survive an add and a failure", () => {
    // A collector who set Foil once must not discover halfway down a box that it stopped applying.
    let state = addSessionReducer(initialState(0), {
      type: "defaults/changed", patch: { finish: "foil" },
    });
    state = applyAdds(state, [{ record: record({ id: "a" }) }]);
    state = addSessionReducer(state, { type: "add/rejected", recordId: "a", reason: "offline" });

    expect(state.carried.finish).toBe("foil");
    expect(state.carried.condition).toBe("near_mint");
  });

  it("announce the change", () => {
    const state = addSessionReducer(initialState(0), {
      type: "defaults/changed", patch: { condition: "lightly_played" },
    });
    expect(state.announcement?.message).toBe("Now adding as lightly_played");
  });

  it("reset only on leaving the session", () => {
    let state = addSessionReducer(initialState(0), {
      type: "defaults/changed", patch: { finish: "foil" },
    });
    state = addSessionReducer(state, { type: "session/reset" });
    expect(state.carried).toEqual(DEFAULT_CARRIED);
    expect(state.records).toEqual([]);
  });
});

describe("tally", () => {
  it("counts pending and confirmed, ignores failed and undone", () => {
    let state = applyAdds(initialState(0), [
      { record: record({ id: "a", delta: 1 }) },
      { record: record({ id: "b", delta: 2 }) },
      { record: record({ id: "c", delta: 4 }) },
    ]);
    state = addSessionReducer(state, { type: "add/rejected", recordId: "b", reason: "x" });
    state = addSessionReducer(state, { type: "undo/applied", recordId: "c" });

    expect(tally(state)).toEqual({ adds: 1, quantity: 1 });
  });

  it("nets a negative delta out of the total", () => {
    // A grid shift-click is an add of −1, and the tally has to read as the session's net effect.
    const state = applyAdds(initialState(0), [
      { record: record({ id: "a", delta: 3 }) },
      { record: record({ id: "b", delta: -1 }) },
    ]);
    expect(tally(state)).toEqual({ adds: 2, quantity: 2 });
  });
});

describe("describe", () => {
  it("uses × for an add and − for a removal", () => {
    expect(describeRecord(record({ delta: 2 }))).toBe("Atlas (FE01 BS1-001) ×2");
    expect(describeRecord(record({ delta: -2 }))).toBe("Atlas (FE01 BS1-001) −2");
  });
});
