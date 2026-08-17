/**
 * The session wired to the network — the rules of `addSessionReducer` and `undoPolicy` as they
 * actually behave against the API, plus the two things only an integration can show:
 *
 *   * the tally moves before the response, and reverts **visibly** when one fails
 *   * undo sends the delta and the expectation ADR-005 requires, computed from what the session
 *     did rather than from a read
 *
 * The API itself is tested against the real FastAPI app in `backend/tests`; what is mocked here is
 * only the transport.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/backend";
import { LiveAnnouncer } from "../components/add/LiveAnnouncer";
import { SessionTally } from "../components/add/SessionTally";
import { AddSessionProvider, useAddSession } from "./AddSessionContext";
import type { CardLabel } from "./types";

const addInventory = vi.hoisted(() => vi.fn());
const adjustInventory = vi.hoisted(() => vi.fn());
const fetchHoldingsFor = vi.hoisted(() => vi.fn());

vi.mock("../api/backend", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/backend")>()),
  addInventory,
  adjustInventory,
  fetchHoldingsFor,
}));

vi.mock("@lars-kluijtmans/react-auth", () => ({
  useAuth: () => ({ getAccessToken: async () => "token" }),
}));

const ATLAS: CardLabel = {
  name: "Atlas", setCode: "FE01", collectorNumber: "BS1-001", finish: "normal",
};
const BORN: CardLabel = {
  name: "Atlasborn", setCode: "FE01", collectorNumber: "BS1-002", finish: "normal",
};

function Driver() {
  const { add, quantityFor } = useAddSession();
  return (
    <>
      <button onClick={() => void add({ printingId: "p1", label: ATLAS })}>add atlas</button>
      <button onClick={() => void add({ printingId: "p2", label: BORN })}>add born</button>
      <button onClick={() => void add({ printingId: "p1", label: ATLAS, delta: -1 })}>
        remove atlas
      </button>
      {/* What a grid badge reads. `null` is "this session has not touched it", which a badge
          renders as the server's own count rather than as zero. */}
      <p data-testid="badge-p1">{String(quantityFor("p1"))}</p>
      <p data-testid="badge-damaged">{String(quantityFor("p1", "damaged"))}</p>
    </>
  );
}

function setup() {
  render(
    <AddSessionProvider>
      <LiveAnnouncer />
      <Driver />
      <SessionTally />
    </AddSessionProvider>,
  );
  return { user: userEvent.setup() };
}

const liveText = (politeness: "polite" | "assertive") =>
  [...document.querySelectorAll(`[aria-live="${politeness}"]`)].map((node) => node.textContent);

const spoken = (politeness: "polite" | "assertive") =>
  liveText(politeness).filter(Boolean).join("");

/** The two figures in the tally, read off their own captions — a bare `getByText("0")` also
 *  matches the other figure, and both are 0 exactly when this matters. */
function tallyFigures() {
  return {
    cards: screen.getByText("cards").previousElementSibling?.textContent,
    adds: screen.getByText("adds").previousElementSibling?.textContent,
  };
}

/** Add once and wait for the server to confirm it. */
async function addOne(user: ReturnType<typeof userEvent.setup>, which = "add atlas") {
  await user.click(screen.getByRole("button", { name: which }));
  await waitFor(() => expect(screen.queryByText("saving")).not.toBeInTheDocument());
}

beforeEach(() => {
  fetchHoldingsFor.mockResolvedValue({ items: [], next_cursor: null, total: 0 });
  let quantity = 0;
  addInventory.mockImplementation(async () => {
    quantity += 1;
    return { item: { id: "item-1", printing_id: "p1", condition: "near_mint", quantity,
                     is_graded: false, updated_at: "2026-08-16T00:00:00Z" }, merged: quantity > 1 };
  });
  adjustInventory.mockResolvedValue({ item_id: "item-1", quantity: 0, deleted: true });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("optimism", () => {
  it("moves the tally before the request resolves", async () => {
    // The network must never gate the next keystroke. If this waits, the ten-minute target for
    // 100 cards is arithmetically out of reach.
    let release: (value: unknown) => void = () => {};
    addInventory.mockReturnValue(new Promise((resolve) => { release = resolve; }));

    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "add atlas" }));

    await waitFor(() => expect(screen.getByText("saving")).toBeInTheDocument());
    expect(screen.getByText("Atlas (FE01 BS1-001) ×1")).toBeInTheDocument();

    release({ item: { id: "item-1", quantity: 1 }, merged: false });
    await waitFor(() => expect(screen.queryByText("saving")).not.toBeInTheDocument());
  });

  it("keeps undo disabled until the row exists", async () => {
    // Disabled rather than hidden, so the list does not shift under the cursor as requests land.
    let release: (value: unknown) => void = () => {};
    addInventory.mockReturnValue(new Promise((resolve) => { release = resolve; }));

    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "add atlas" }));
    await waitFor(() => expect(screen.getByText("saving")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Undo" })).toBeDisabled();

    release({ item: { id: "item-1", quantity: 1 }, merged: false });
    await waitFor(() => expect(screen.getByRole("button", { name: "Undo" })).toBeEnabled());
  });
});

describe("a failed add", () => {
  it("reverts the tally and names the card on screen", async () => {
    // A collector who does not notice a failure has a wrong collection and no way to find out.
    addInventory.mockRejectedValue(new ApiError(503, "unavailable", "the backend is down"));

    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "add atlas" }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent("the backend is down");
    // Nothing counted, and the failed record stays on the list rather than vanishing silently.
    expect(tallyFigures()).toEqual({ cards: "0", adds: "0" });
    expect(screen.getByText("Atlas (FE01 BS1-001) ×1")).toBeInTheDocument();
  });

  it("says so in the assertive region, not the polite one", async () => {
    addInventory.mockRejectedValue(new ApiError(503, "unavailable", "the backend is down"));

    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "add atlas" }));

    await waitFor(() => expect(spoken("assertive")).toContain("Could not add Atlas"));
    expect(spoken("polite")).toBe("");
  });

  it("survives an error that is not an ApiError", async () => {
    addInventory.mockRejectedValue(new TypeError("network"));

    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "add atlas" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("the request failed"));
  });
});

describe("undo sends a delta and an expectation", () => {
  it("undoing one of three adds expects three", async () => {
    // **The ADR-005 assertion.** Not "expected 1" (what it was before this add) and not a
    // read-then-write — the expectation is computed from what this session did.
    const { user } = setup();
    await addOne(user);
    await addOne(user);
    await addOne(user);

    await user.click(screen.getAllByRole("button", { name: "Undo" })[0]);

    await waitFor(() => expect(adjustInventory).toHaveBeenCalledTimes(1));
    expect(adjustInventory.mock.calls[0][0]).toBe("item-1");
    expect(adjustInventory.mock.calls[0][1]).toEqual({ delta: -1, expected_quantity: 3 });
  });

  it("counts a pre-existing holding into the expectation", async () => {
    // The baseline is what the row held before this session touched it, so an undo against a
    // holding that already had two copies expects three, not one.
    fetchHoldingsFor.mockResolvedValue({
      items: [{ id: "item-1", printing_id: "p1", condition: "near_mint", quantity: 2,
                is_graded: false, updated_at: "2026-08-16T00:00:00Z" }],
      next_cursor: null, total: 1,
    });

    const { user } = setup();
    await addOne(user);
    await user.click(screen.getByRole("button", { name: "Undo" }));

    await waitFor(() => expect(adjustInventory).toHaveBeenCalled());
    expect(adjustInventory.mock.calls[0][1]).toEqual({ delta: -1, expected_quantity: 3 });
  });

  it("ignores a graded row when reading the baseline", async () => {
    // A PSA 9 is its own row and its own object. Counting it into an ungraded holding's baseline
    // would make every undo on that holding refuse.
    fetchHoldingsFor.mockResolvedValue({
      items: [{ id: "graded-1", printing_id: "p1", condition: "near_mint", quantity: 1,
                is_graded: true, updated_at: "2026-08-16T00:00:00Z" }],
      next_cursor: null, total: 1,
    });

    const { user } = setup();
    await addOne(user);
    await user.click(screen.getByRole("button", { name: "Undo" }));

    await waitFor(() => expect(adjustInventory).toHaveBeenCalled());
    expect(adjustInventory.mock.calls[0][1]).toEqual({ delta: -1, expected_quantity: 1 });
  });

  it("reads a holding's baseline once, however many times it is added", async () => {
    const { user } = setup();
    await addOne(user);
    await addOne(user);
    await addOne(user);

    expect(fetchHoldingsFor).toHaveBeenCalledTimes(1);
  });

  it("treats an unreadable baseline as zero rather than blocking the add", async () => {
    // The consequence is contained: undo will refuse rather than guess, which is the behaviour
    // story 018 asks for anyway. Refusing to *add* because a read failed would not be.
    fetchHoldingsFor.mockRejectedValue(new ApiError(503, "unavailable", "down"));

    const { user } = setup();
    await addOne(user);

    expect(addInventory).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Atlas (FE01 BS1-001) ×1")).toBeInTheDocument();
  });

  it("strikes the record through and announces it politely once it lands", async () => {
    const { user } = setup();
    await addOne(user);
    await user.click(screen.getByRole("button", { name: "Undo" }));

    await waitFor(() => expect(spoken("polite")).toContain("Undid Atlas (FE01 BS1-001) ×1"));
    // The undo control is gone for that record — there is nothing left to take back.
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });
});

describe("the server refuses an undo", () => {
  it("reports both numbers and leaves the add counted", async () => {
    // Somebody moved the row in another tab. Story 018: refuse with an explanation rather than
    // guess, so the collector knows whether their collection is now right.
    adjustInventory.mockRejectedValue(
      new ApiError(409, "inventory_item_changed", "That holding changed since you added it",
                   { expected: 1, actual: 5 }),
    );

    const { user } = setup();
    await addOne(user);
    await user.click(screen.getByRole("button", { name: "Undo" }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("expected 1, found 5");
    expect(alert).toHaveTextContent("Nothing was changed");

    // Still one card. A refusal that quietly decremented the tally would be the worst of both.
    expect(tallyFigures()).toEqual({ cards: "1", adds: "1" });
    expect(spoken("assertive")).toContain("Could not undo");
  });

  it("falls back to the session's own expectation when details are missing", async () => {
    adjustInventory.mockRejectedValue(
      new ApiError(409, "inventory_item_changed", "changed", {}),
    );

    const { user } = setup();
    await addOne(user);
    await user.click(screen.getByRole("button", { name: "Undo" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("expected 1"));
  });

  it("reports any other failure as a plain failure", async () => {
    adjustInventory.mockRejectedValue(new ApiError(500, "error", "server exploded"));

    const { user } = setup();
    await addOne(user);
    await user.click(screen.getByRole("button", { name: "Undo" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("server exploded"));
  });
});

describe("removing from the grid", () => {
  it("a shift-click at zero is a quiet no-op, not an error flash", async () => {
    // The user was aiming at a different tile. A red banner for a missed click is noise.
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "remove atlas" }));

    await waitFor(() => expect(screen.getByText("nothing to remove")).toBeInTheDocument());
    expect(adjustInventory).not.toHaveBeenCalled();
    expect(spoken("assertive")).toContain("nothing to remove");
  });

  it("a shift-click on an owned holding adjusts by −1", async () => {
    fetchHoldingsFor.mockResolvedValue({
      items: [{ id: "item-1", printing_id: "p1", condition: "near_mint", quantity: 3,
                is_graded: false, updated_at: "2026-08-16T00:00:00Z" }],
      next_cursor: null, total: 1,
    });
    adjustInventory.mockResolvedValue({ item_id: "item-1", quantity: 2, deleted: false });

    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "remove atlas" }));

    await waitFor(() => expect(adjustInventory).toHaveBeenCalled());
    expect(adjustInventory.mock.calls[0][1]).toEqual({ delta: -1, expected_quantity: 3 });
  });
});

describe("what a grid badge reads", () => {
  it("is null until this session touches the holding", async () => {
    // Not zero. Zero would claim the collector owns none of a card the server may well have.
    setup();
    expect(screen.getByTestId("badge-p1")).toHaveTextContent("null");
  });

  it("moves on the click, before the response", async () => {
    let release: (value: unknown) => void = () => {};
    addInventory.mockReturnValue(new Promise((resolve) => { release = resolve; }));

    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "add atlas" }));

    await waitFor(() => expect(screen.getByTestId("badge-p1")).toHaveTextContent("1"));
    release({ item: { id: "item-1", quantity: 1 }, merged: false });
  });

  it("counts the baseline the holding already had", async () => {
    fetchHoldingsFor.mockResolvedValue({
      items: [{ id: "item-1", printing_id: "p1", condition: "near_mint", quantity: 4,
                is_graded: false, updated_at: "2026-08-16T00:00:00Z" }],
      next_cursor: null, total: 1,
    });

    const { user } = setup();
    await addOne(user);
    expect(screen.getByTestId("badge-p1")).toHaveTextContent("5");
  });

  it("drops an undone add back out of the count", async () => {
    const { user } = setup();
    await addOne(user);
    await addOne(user);
    expect(screen.getByTestId("badge-p1")).toHaveTextContent("2");

    await user.click(screen.getAllByRole("button", { name: "Undo" })[0]);
    await waitFor(() => expect(screen.getByTestId("badge-p1")).toHaveTextContent("1"));
  });

  it("reads per condition, not per printing", async () => {
    // The same card in another condition is another holding, and its badge must not inherit
    // this one's count.
    const { user } = setup();
    await addOne(user);

    expect(screen.getByTestId("badge-p1")).toHaveTextContent("1");
    expect(screen.getByTestId("badge-damaged")).toHaveTextContent("null");
  });
});

describe("the live regions", () => {
  it("announce two identical adds in a row rather than falling silent on the second", async () => {
    // The case a collector emptying a box of duplicates hits immediately. A single region would
    // be mutated from "Added Atlas ×1" to "Added Atlas ×1" — no change, no announcement.
    const { user } = setup();
    await addOne(user);
    const first = liveText("polite");

    await addOne(user);
    const second = liveText("polite");

    const message = "Added Atlas (FE01 BS1-001) ×1";
    // Exactly one region speaks at a time, and it is the *other* one the second time — so both
    // slots mutated, one of them from empty to text, which is what a screen reader reads out.
    expect(first.filter(Boolean)).toEqual([message]);
    expect(second.filter(Boolean)).toEqual([message]);
    expect(first.indexOf(message)).not.toBe(second.indexOf(message));
  });

  it("never speak in both politenesses at once", async () => {
    const { user } = setup();
    await addOne(user);

    expect(spoken("polite")).toContain("Added Atlas");
    expect(spoken("assertive")).toBe("");
  });
});

describe("the provider", () => {
  it("refuses to be used without one", () => {
    // A silent no-op session would look like a working page that loses every add.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<SessionTally />)).toThrow(/AddSessionProvider/);
    spy.mockRestore();
  });
});
