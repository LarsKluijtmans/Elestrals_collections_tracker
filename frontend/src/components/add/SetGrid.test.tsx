/**
 * Whole-set entry — story 017. Click is +1, shift-click is −1, and a burst is one add.
 *
 * The badge assertions are about optimism: a tile has to update on the *click*, not on the
 * response, or sweeping a set feels broken even when every request succeeds.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SetChecklistEntry } from "../../api/backend";
import { COALESCE_MS } from "../../session/deltaCoalescer";
import { SetGrid } from "./SetGrid";

function entry(n: number): SetChecklistEntry {
  return {
    card_id: `c${n}`,
    collector_number: `FE01-00${n}`,
    name: `Card ${n}`,
    element: "earth",
    card_type: "elestral",
    printings: [{
      printing_id: `p${n}`, rarity: "common", finish: "normal", language: "en",
      edition: "first", image_url: null, alt_text: `Card ${n} — FE01 common`,
    }],
  };
}

const ENTRIES = [entry(1), entry(2), entry(3)];

const add = vi.hoisted(() => vi.fn());
const quantityFor = vi.hoisted(() => vi.fn());
vi.mock("../../session/AddSessionContext", () => ({
  useAddSession: () => ({ add, quantityFor }),
}));

/** Long enough for the coalescing window to close, with room for a slow CI box. */
const settle = () => new Promise((resolve) => setTimeout(resolve, COALESCE_MS + 150));

function setup() {
  const view = render(<SetGrid entries={ENTRIES} />);
  return { user: userEvent.setup(), view };
}

beforeEach(() => {
  quantityFor.mockReturnValue(null);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("clicking tiles", () => {
  it("a click is +1", async () => {
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: /Card 1\./ }));
    await settle();

    expect(add).toHaveBeenCalledTimes(1);
    expect(add.mock.calls[0][0]).toMatchObject({ printingId: "p1", delta: 1 });
  });

  it("a shift-click is −1", async () => {
    const { user } = setup();
    await user.keyboard("{Shift>}");
    await user.click(screen.getByRole("button", { name: /Card 2\./ }));
    await user.keyboard("{/Shift}");
    await settle();

    expect(add).toHaveBeenCalledTimes(1);
    expect(add.mock.calls[0][0]).toMatchObject({ printingId: "p2", delta: -1 });
  });

  it("carries the card's label so a failure can name it", async () => {
    // "Could not add that one" is not a failure message, and the label has to be captured at
    // click time — a fetch to find the name may fail for the same reason the add did.
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: /Card 3\./ }));
    await settle();

    expect(add.mock.calls[0][0].label).toEqual({
      name: "Card 3", setCode: "FE01", collectorNumber: "FE01-003", finish: "normal",
    });
  });
});

describe("coalescing a burst", () => {
  it("three clicks on one tile are one add of +3", async () => {
    // Not only one request — **one undo entry**. Three entries of +1 would make a collector who
    // mis-clicked press undo three times.
    const { user } = setup();
    const tile = screen.getByRole("button", { name: /Card 1\./ });

    await user.click(tile);
    await user.click(tile);
    await user.click(tile);
    await settle();

    expect(add).toHaveBeenCalledTimes(1);
    expect(add.mock.calls[0][0].delta).toBe(3);
  });

  it("a click and a shift-click on one tile send nothing", async () => {
    // A burst that nets to zero has nothing to record, and an entry that undoes to itself is
    // worse than no entry.
    const { user } = setup();
    const tile = screen.getByRole("button", { name: /Card 1\./ });

    await user.click(tile);
    await user.keyboard("{Shift>}");
    await user.click(tile);
    await user.keyboard("{/Shift}");
    await settle();

    expect(add).not.toHaveBeenCalled();
  });

  it("two different tiles are two adds, not one delayed behind the other", async () => {
    // The grid is meant to be swept across.
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: /Card 1\./ }));
    await user.click(screen.getByRole("button", { name: /Card 2\./ }));
    await settle();

    expect(add).toHaveBeenCalledTimes(2);
    expect(add.mock.calls.map((call) => call[0].printingId).sort()).toEqual(["p1", "p2"]);
  });

  it("sends a pending burst when the page unmounts", async () => {
    // Navigating away mid-burst must not lose clicks the collector already made.
    const { user, view } = setup();
    await user.click(screen.getByRole("button", { name: /Card 1\./ }));

    view.unmount();

    expect(add).toHaveBeenCalledTimes(1);
    expect(add.mock.calls[0][0].delta).toBe(1);
  });
});

describe("what a tile says", () => {
  it("shows the session's own count, so it updates on click", async () => {
    quantityFor.mockImplementation((printingId: string) => (printingId === "p1" ? 4 : null));
    setup();

    expect(screen.getByRole("button", { name: /Card 1\. 4 owned/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Card 2\. 0 owned/ })).toBeInTheDocument();
  });

  it("states both interactions in the accessible name", async () => {
    // Shift-click is not discoverable by a screen reader otherwise, and the grid is then
    // add-only for anyone using one.
    setup();
    const tile = screen.getByRole("button", { name: /Card 1\./ });
    expect(tile).toHaveAccessibleName(/Click to add, shift-click to remove/);
  });

  it("gives the art its alt text rather than leaving it unlabelled", async () => {
    setup();
    expect(screen.getByRole("img", { name: "Card 1 — FE01 common" })).toBeInTheDocument();
  });

  it("renders nothing for an entry with no printings", async () => {
    // A card row with no printing cannot be added, so a tile for it would be a dead target.
    render(<SetGrid entries={[{ ...entry(9), printings: [] }]} />);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });
});
