// Every state transition from stage 1, pure and in one place.
//
// No I/O here on purpose. If a rule needs a component rendered or a network mocked to test it,
// it has been put in the wrong layer — and the rules in this file are the ones that decide
// whether a collector's data is right.
import {
  DEFAULT_CARRIED, holdingKey, UNDO_LIMIT,
  type AddRecord, type AddSessionAction, type AddSessionState,
} from "./types";
import { refusalMessage } from "./undoPolicy";

export function initialState(now = Date.now()): AddSessionState {
  return {
    carried: DEFAULT_CARRIED,
    records: [],
    touched: {},
    announcement: null,
    startedAt: now,
  };
}

export function addSessionReducer(
  state: AddSessionState,
  action: AddSessionAction,
): AddSessionState {
  switch (action.type) {
    case "add/applied": {
      const key = holdingKey(action.record.printingId, action.record.condition);
      // The baseline is recorded ONCE, on first touch. Overwriting it on a later add would make
      // it mean "before the most recent add", and `expectedQuantity` would then double-count
      // every earlier delta.
      const touched = state.touched[key] ?? {
        key,
        printingId: action.record.printingId,
        condition: action.record.condition,
        baselineQuantity: action.baselineQuantity,
      };

      return {
        ...state,
        // The tally moves NOW, not on response. The network must never gate the next keystroke —
        // that is the whole product thesis.
        records: capStack([action.record, ...state.records]),
        touched: { ...state.touched, [key]: touched },
        announcement: announce(state, `Added ${describe(action.record)}`, false),
      };
    }

    case "add/confirmed": {
      const key = keyOfRecord(state, action.recordId);
      return {
        ...state,
        records: state.records.map((record) =>
          record.id === action.recordId
            ? { ...record, state: "confirmed", itemId: action.itemId }
            : record,
        ),
        touched: key
          ? { ...state.touched, [key]: { ...state.touched[key], itemId: action.itemId } }
          : state.touched,
        announcement: state.announcement,
      };
    }

    case "add/rejected": {
      const record = state.records.find((r) => r.id === action.recordId);
      return {
        ...state,
        records: state.records.map((r) =>
          r.id === action.recordId ? { ...r, state: "failed", reason: action.reason } : r,
        ),
        // Rollback is VISIBLE and names the card. A collector who does not notice a failure has
        // a wrong collection and no way to find out — silence is the one unacceptable outcome.
        announcement: announce(
          state,
          record
            ? `Could not add ${describe(record)}: ${action.reason}`
            : `An add failed: ${action.reason}`,
          true,
        ),
      };
    }

    case "undo/applied": {
      const record = state.records.find((r) => r.id === action.recordId);
      return {
        ...state,
        records: state.records.map((r) =>
          r.id === action.recordId ? { ...r, state: "undone" } : r,
        ),
        announcement: announce(state, record ? `Undid ${describe(record)}` : "Undid an add", false),
      };
    }

    case "undo/refused": {
      const record = state.records.find((r) => r.id === action.recordId);
      const label = record ? describe(record) : "that add";
      return {
        ...state,
        records: state.records.map((r) =>
          r.id === action.recordId
            ? { ...r, reason: refusalMessage(label, action.expected, action.actual) }
            : r,
        ),
        announcement: announce(state, refusalMessage(label, action.expected, action.actual), true),
      };
    }

    case "defaults/changed":
      // Carried defaults survive an add and a failure. They reset only on leaving the session —
      // a collector who set Foil once should never discover halfway down a box that it stopped
      // applying.
      return {
        ...state,
        carried: { ...state.carried, ...action.patch },
        announcement: announce(
          state,
          `Now adding as ${Object.values(action.patch).join(", ")}`,
          false,
        ),
      };

    case "session/reset":
      return initialState();

    default:
      return state;
  }
}

/** FIFO eviction at the cap. The oldest entry ages out rather than the newest being refused. */
function capStack(records: AddRecord[]): AddRecord[] {
  return records.slice(0, UNDO_LIMIT);
}

function keyOfRecord(state: AddSessionState, recordId: string): string | null {
  const record = state.records.find((r) => r.id === recordId);
  return record ? holdingKey(record.printingId, record.condition) : null;
}

function announce(state: AddSessionState, message: string, assertive: boolean) {
  // `seq` is part of the value so two identical messages in a row are still distinguishable —
  // without it a screen reader stays silent on the second of two identical adds, which is exactly
  // the case a collector emptying a box of duplicates will hit.
  //
  // It counts rather than timestamps. `Date.now()` was the first attempt and the test stage caught
  // it: two adds inside one millisecond produced the same value, so the guarantee was really a
  // probability that got worse the faster the flow got — in the flow whose entire purpose is
  // speed. Deriving it from the previous announcement keeps the reducer pure and the value
  // strictly increasing.
  return { message, assertive, seq: (state.announcement?.seq ?? 0) + 1 };
}

export function describe(record: AddRecord): string {
  const { name, setCode, collectorNumber } = record.label;
  const quantity = Math.abs(record.delta);
  const verb = record.delta < 0 ? "−" : "×";
  return `${name} (${setCode} ${collectorNumber}) ${verb}${quantity}`;
}

// --- derived views -------------------------------------------------------------------

/** Total adds and total quantity, counting pending records — that is what optimistic means. */
export function tally(state: AddSessionState): { adds: number; quantity: number } {
  const live = state.records.filter((r) => r.state === "pending" || r.state === "confirmed");
  return {
    adds: live.length,
    quantity: live.reduce((total, record) => total + record.delta, 0),
  };
}

export function recentAdds(state: AddSessionState, count = 5): AddRecord[] {
  return state.records.slice(0, count);
}

/** The most recent record that could be undone — what `Ctrl+Z` acts on. */
export function lastUndoable(state: AddSessionState): AddRecord | null {
  return state.records.find((r) => r.state === "confirmed" && r.itemId) ?? null;
}
