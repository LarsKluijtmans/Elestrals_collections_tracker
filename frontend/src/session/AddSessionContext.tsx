import { useAuth } from "@lars-kluijtmans/react-auth";
import {
  createContext, useCallback, useContext, useMemo, useReducer, useRef, type ReactNode,
} from "react";
import { addInventory, adjustInventory, ApiError, fetchHoldingsFor } from "../api/backend";
import { addSessionReducer, describe, initialState, lastUndoable, recentAdds, tally } from "./addSessionReducer";
import { canUndo } from "./undoPolicy";
import {
  holdingKey, type AddRecord, type CardLabel, type CarriedDefaults, type Condition,
} from "./types";

/**
 * The add session — the aggregate from stage 1, wired to the network.
 *
 * Lives above both entry surfaces (`/collection/add` and `/collection/add/set/:code`) because
 * they **share one session**: the carried condition, the tally and the undo stack survive moving
 * between them. A provider inside either page would die on that navigation, which is the bug this
 * placement exists to prevent.
 *
 * The reducer owns every rule; this owns the I/O and nothing else. That split is what makes the
 * rules testable without a DOM.
 */

type AddSessionValue = {
  carried: CarriedDefaults;
  records: AddRecord[];
  recent: AddRecord[];
  tally: { adds: number; quantity: number };
  announcement: { message: string; assertive: boolean; seq: number } | null;
  add(input: { printingId: string; label: CardLabel; delta?: number }): Promise<void>;
  undo(recordId: string): Promise<void>;
  undoLast(): Promise<void>;
  changeDefaults(patch: Partial<CarriedDefaults>): void;
  canUndoRecord(record: AddRecord): { allowed: boolean; reason?: string };
  /** Live per-printing quantity as this session believes it — drives the grid badges without a
   *  refetch, so a tile updates on click rather than on response. */
  quantityFor(printingId: string, condition?: Condition): number | null;
};

const AddSessionCtx = createContext<AddSessionValue | null>(null);

export function AddSessionProvider({ children }: { children: ReactNode }) {
  const { getAccessToken } = useAuth();
  const [state, dispatch] = useReducer(addSessionReducer, undefined, () => initialState());

  // Read through a ref inside async callbacks: by the time a response lands, the `state` closed
  // over at call time is stale, and `expectedQuantity` computed from stale records is exactly
  // the bug ADR-005 exists to prevent.
  const stateRef = useRef(state);
  stateRef.current = state;

  /** A holding's quantity before this session first touched it. Fetched once per holding. */
  const baselineFor = useCallback(
    async (printingId: string, condition: Condition): Promise<{ qty: number; itemId?: string }> => {
      const known = stateRef.current.touched[holdingKey(printingId, condition)];
      if (known) return { qty: known.baselineQuantity, itemId: known.itemId };

      try {
        const page = await fetchHoldingsFor(printingId, getAccessToken);
        const row = page.items.find((item) => item.condition === condition && !item.is_graded);
        return { qty: row?.quantity ?? 0, itemId: row?.id };
      } catch {
        // A baseline we could not read is a baseline of zero, and the consequence is contained:
        // undo will refuse rather than guess, which is the behaviour story 018 asks for anyway.
        return { qty: 0 };
      }
    },
    [getAccessToken],
  );

  const add = useCallback<AddSessionValue["add"]>(
    async ({ printingId, label, delta = 1 }) => {
      if (delta === 0) return;
      const carried = stateRef.current.carried;
      const baseline = await baselineFor(printingId, carried.condition);

      const record: AddRecord = {
        id: crypto.randomUUID(),
        printingId,
        condition: carried.condition,
        delta,
        state: "pending",
        appliedAt: Date.now(),
        label,
      };
      // Optimistic: the tally moves before the request leaves. Adds are fired concurrently and
      // never queued — which is exactly why bolt 004's upsert had to be atomic.
      dispatch({ type: "add/applied", record, baselineQuantity: baseline.qty });

      try {
        if (delta > 0) {
          const result = await addInventory(
            { printing_id: printingId, condition: carried.condition, quantity: delta },
            getAccessToken,
          );
          dispatch({
            type: "add/confirmed",
            recordId: record.id,
            itemId: result.item.id,
            quantity: result.item.quantity,
          });
        } else {
          if (!baseline.itemId) {
            // Shift-click at zero. A no-op, not an error flash — the user was aiming at a
            // different tile, and a red banner for a missed click is noise.
            dispatch({ type: "add/rejected", recordId: record.id, reason: "nothing to remove" });
            return;
          }
          const result = await adjustInventory(
            baseline.itemId,
            { delta, expected_quantity: baseline.qty },
            getAccessToken,
          );
          dispatch({
            type: "add/confirmed",
            recordId: record.id,
            itemId: result.item_id,
            quantity: result.quantity,
          });
        }
      } catch (error) {
        dispatch({
          type: "add/rejected",
          recordId: record.id,
          reason: error instanceof ApiError ? error.message : "the request failed",
        });
      }
    },
    [baselineFor, getAccessToken],
  );

  const undo = useCallback<AddSessionValue["undo"]>(
    async (recordId) => {
      const current = stateRef.current;
      const record = current.records.find((r) => r.id === recordId);
      if (!record) return;

      const verdict = canUndo(current, record);
      if (!verdict.allowed) {
        // Refused locally, instantly, with a reason — no round trip needed to say "that add
        // never went through".
        dispatch({ type: "add/rejected", recordId, reason: verdict.reason });
        return;
      }

      try {
        await adjustInventory(
          verdict.itemId,
          { delta: -record.delta, expected_quantity: verdict.expectedQuantity },
          getAccessToken,
        );
        dispatch({ type: "undo/applied", recordId });
      } catch (error) {
        if (error instanceof ApiError && error.code === "inventory_item_changed") {
          // The server's compare-and-swap refused: somebody else moved the row. Nothing was
          // changed, and the message says what was expected and what was found.
          const details = error.details as { expected?: number; actual?: number };
          dispatch({
            type: "undo/refused",
            recordId,
            expected: details.expected ?? verdict.expectedQuantity,
            actual: details.actual ?? -1,
          });
          return;
        }
        dispatch({
          type: "add/rejected",
          recordId,
          reason: error instanceof ApiError ? error.message : "the undo failed",
        });
      }
    },
    [getAccessToken],
  );

  const undoLast = useCallback(async () => {
    const record = lastUndoable(stateRef.current);
    if (record) await undo(record.id);
  }, [undo]);

  const value = useMemo<AddSessionValue>(
    () => ({
      carried: state.carried,
      records: state.records,
      recent: recentAdds(state),
      tally: tally(state),
      announcement: state.announcement,
      add,
      undo,
      undoLast,
      changeDefaults: (patch) => dispatch({ type: "defaults/changed", patch }),
      canUndoRecord: (record) => {
        const verdict = canUndo(state, record);
        return verdict.allowed ? { allowed: true } : { allowed: false, reason: verdict.reason };
      },
      quantityFor: (printingId, condition) => {
        const holding = state.touched[holdingKey(printingId, condition ?? state.carried.condition)];
        if (!holding) return null;
        return state.records
          .filter(
            (r) =>
              holdingKey(r.printingId, r.condition) === holding.key &&
              r.state !== "undone" &&
              r.state !== "failed",
          )
          .reduce((total, r) => total + r.delta, holding.baselineQuantity);
      },
    }),
    [state, add, undo, undoLast],
  );

  return <AddSessionCtx.Provider value={value}>{children}</AddSessionCtx.Provider>;
}

export function useAddSession(): AddSessionValue {
  const value = useContext(AddSessionCtx);
  if (!value) throw new Error("useAddSession must be used inside an AddSessionProvider");
  return value;
}

export { describe };
