/**
 * Rapid clicks on one grid tile become one add — story 017's debounce, promoted to a domain rule.
 *
 * The consequence is not only network traffic: three clicks in 300ms must be **one** undo entry
 * of +3, not three of +1. Otherwise a collector who mis-clicked four times has to press undo four
 * times, and the undo stack is a keystroke log.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { COALESCE_MS, createCoalescer } from "./deltaCoalescer";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("createCoalescer", () => {
  it("sends one add for a burst on one tile", () => {
    const flush = vi.fn();
    const coalescer = createCoalescer(flush);

    coalescer.push("p1", 1);
    coalescer.push("p1", 1);
    coalescer.push("p1", 1);
    vi.advanceTimersByTime(COALESCE_MS);

    expect(flush).toHaveBeenCalledTimes(1);
    expect(flush).toHaveBeenCalledWith("p1", 3);
  });

  it("holds nothing back once the window has passed", () => {
    const flush = vi.fn();
    const coalescer = createCoalescer(flush);

    coalescer.push("p1", 1);
    vi.advanceTimersByTime(COALESCE_MS);
    coalescer.push("p1", 1);
    vi.advanceTimersByTime(COALESCE_MS);

    expect(flush).toHaveBeenCalledTimes(2);
    expect(flush).toHaveBeenNthCalledWith(2, "p1", 1);
  });

  it("nets a click and a shift-click to nothing at all", () => {
    // There is no such thing as a zero delta, and recording one would put an entry in the undo
    // stack that undoes to itself.
    const flush = vi.fn();
    const coalescer = createCoalescer(flush);

    coalescer.push("p1", 1);
    coalescer.push("p1", -1);
    vi.advanceTimersByTime(COALESCE_MS);

    expect(flush).not.toHaveBeenCalled();
  });

  it("nets a mixed burst to its sum", () => {
    const flush = vi.fn();
    const coalescer = createCoalescer(flush);

    coalescer.push("p1", 1);
    coalescer.push("p1", 1);
    coalescer.push("p1", -1);
    coalescer.push("p1", 1);
    vi.advanceTimersByTime(COALESCE_MS);

    expect(flush).toHaveBeenCalledWith("p1", 2);
  });

  it("debounces per printing, not globally", () => {
    // Clicking two different tiles quickly should send two adds, not delay the first behind
    // the second — the grid is meant to be swept across.
    const flush = vi.fn();
    const coalescer = createCoalescer(flush);

    coalescer.push("p1", 1);
    coalescer.push("p2", 1);
    vi.advanceTimersByTime(COALESCE_MS);

    expect(flush).toHaveBeenCalledTimes(2);
    expect(flush).toHaveBeenCalledWith("p1", 1);
    expect(flush).toHaveBeenCalledWith("p2", 1);
  });

  it("keeps deferring while the clicks keep coming", () => {
    const flush = vi.fn();
    const coalescer = createCoalescer(flush);

    coalescer.push("p1", 1);
    vi.advanceTimersByTime(COALESCE_MS - 50);
    coalescer.push("p1", 1);
    vi.advanceTimersByTime(COALESCE_MS - 50);
    expect(flush).not.toHaveBeenCalled();

    vi.advanceTimersByTime(50);
    expect(flush).toHaveBeenCalledWith("p1", 2);
  });

  it("flushAll sends a pending burst immediately", () => {
    // What unmount calls. Clicks a collector already made must not be lost to navigation.
    const flush = vi.fn();
    const coalescer = createCoalescer(flush);

    coalescer.push("p1", 2);
    coalescer.push("p2", 1);
    coalescer.flushAll();

    expect(flush).toHaveBeenCalledTimes(2);
  });

  it("flushAll does not double-send when the timer would also have fired", () => {
    const flush = vi.fn();
    const coalescer = createCoalescer(flush);

    coalescer.push("p1", 1);
    coalescer.flushAll();
    vi.advanceTimersByTime(COALESCE_MS * 2);

    expect(flush).toHaveBeenCalledTimes(1);
  });

  it("cancel drops everything pending", () => {
    const flush = vi.fn();
    const coalescer = createCoalescer(flush);

    coalescer.push("p1", 1);
    coalescer.cancel();
    vi.advanceTimersByTime(COALESCE_MS * 2);

    expect(flush).not.toHaveBeenCalled();
  });

  it("accepts a custom window", () => {
    const flush = vi.fn();
    const coalescer = createCoalescer(flush, 50);

    coalescer.push("p1", 1);
    vi.advanceTimersByTime(50);

    expect(flush).toHaveBeenCalledWith("p1", 1);
  });
});
