// Rapid clicks on one grid tile become one add.
//
// Story 017 asks for the request to be debounced. Stage 1 went further and made it a domain rule,
// because the consequence is not only network: three clicks in 300ms must be **one** undo entry
// of +3, not three of +1. Anything else turns the undo stack into a keystroke log, and a
// collector who clicked four times by accident has to press undo four times to fix it.
//
// A burst that nets to zero — click, shift-click — sends nothing at all. There is no such thing
// as a zero delta, and recording one would put an entry in the stack that undoes to itself.

export type CoalescedFlush = (printingId: string, delta: number) => void;

export type Coalescer = {
  push(printingId: string, delta: number): void;
  /** Send everything pending immediately — on unmount, or before navigating away. */
  flushAll(): void;
  cancel(): void;
};

export const COALESCE_MS = 300;

export function createCoalescer(flush: CoalescedFlush, windowMs = COALESCE_MS): Coalescer {
  const pending = new Map<string, number>();
  const timers = new Map<string, ReturnType<typeof setTimeout>>();

  function send(printingId: string): void {
    const delta = pending.get(printingId) ?? 0;
    pending.delete(printingId);
    const timer = timers.get(printingId);
    if (timer) clearTimeout(timer);
    timers.delete(printingId);
    if (delta !== 0) flush(printingId, delta);
  }

  return {
    push(printingId, delta) {
      pending.set(printingId, (pending.get(printingId) ?? 0) + delta);
      // Per printing, not global: clicking two different tiles quickly should send two requests,
      // not delay the first one behind the second.
      const existing = timers.get(printingId);
      if (existing) clearTimeout(existing);
      timers.set(printingId, setTimeout(() => send(printingId), windowMs));
    },

    flushAll() {
      for (const printingId of [...pending.keys()]) send(printingId);
    },

    cancel() {
      for (const timer of timers.values()) clearTimeout(timer);
      timers.clear();
      pending.clear();
    },
  };
}
