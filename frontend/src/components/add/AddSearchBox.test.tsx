/**
 * The keyboard contract — bolt 005's named success criterion.
 *
 *   focus on load · type → ↓ → Enter → cleared and refocused · Esc clears · Ctrl+Z undoes
 *
 * This is the single interaction the product is judged on: median add under five seconds, 100
 * cards in ten minutes, hands never leaving the keyboard. A regression here does not look like a
 * bug, it looks like the product being slow — so every step of the sequence is pinned.
 *
 * `test_enter_waits_for_an_in_flight_search` is the one that would otherwise ship broken: acting
 * on the previous result set adds **the wrong card**, silently, at speed.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CardSearchResult } from "../../api/backend";
import { AddSearchBox } from "./AddSearchBox";

const ATLAS: CardSearchResult = {
  card_id: "c1", name: "Atlas", set_code: "FE01", collector_number: "BS1-001",
  card_type: "elestral", element: "earth", printing_count: 1, match_kind: "exact_name",
  primary_printing: {
    printing_id: "p1", rarity: "rare", finish: "normal", language: "en",
    edition: "first", image_url: null, alt_text: "Atlas — FE01 rare",
  },
};

const ATLASBORN: CardSearchResult = {
  ...ATLAS,
  card_id: "c2", name: "Atlasborn", collector_number: "BS1-002",
  primary_printing: { ...ATLAS.primary_printing!, printing_id: "p2" },
};

const NO_PRINTINGS: CardSearchResult = {
  ...ATLAS, card_id: "c3", name: "Teratlas", collector_number: "BS1-003", primary_printing: null,
};

/** Only ever in the *second* result set, so "which set did Enter act on" has a single answer. */
const LATE_ARRIVAL: CardSearchResult = {
  ...ATLAS,
  card_id: "c9", name: "Atlas Shard", collector_number: "BS1-009",
  primary_printing: { ...ATLAS.primary_printing!, printing_id: "p9" },
};

const searchCards = vi.hoisted(() => vi.fn());
vi.mock("../../api/backend", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/backend")>()),
  searchCards,
}));

// The session is mocked so this file is only about the keys. What the session then *does* with an
// add is `AddSessionContext.test.tsx`'s subject.
const add = vi.hoisted(() => vi.fn());
const undoLast = vi.hoisted(() => vi.fn());
vi.mock("../../session/AddSessionContext", () => ({
  useAddSession: () => ({
    add, undoLast,
    carried: { condition: "lightly_played", finish: "foil", language: "en", edition: "unlimited" },
  }),
}));

function page(items: CardSearchResult[] = [ATLAS, ATLASBORN, NO_PRINTINGS]) {
  return { items, next_cursor: null, total: items.length };
}

function setup() {
  render(<AddSearchBox />);
  return { user: userEvent.setup(), input: screen.getByRole("combobox") };
}

async function typeAndWait(user: ReturnType<typeof userEvent.setup>, term: string, rows = 3) {
  await user.type(screen.getByRole("combobox"), term);
  await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(rows));
}

beforeEach(() => {
  searchCards.mockResolvedValue(page());
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("starting without touching the mouse", () => {
  it("puts focus in the field on load", () => {
    // A collector with a box on the desk should not have to click anything to start.
    const { input } = setup();
    expect(input).toHaveFocus();
  });

  it("states the carried condition and finish on the field itself", () => {
    // So a whole box does not go in as Near Mint Normal because the bar was off screen.
    setup();
    expect(screen.getByLabelText(/lightly played/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/foil/i)).toBeInTheDocument();
  });
});

describe("searching", () => {
  it("does not query below three characters", async () => {
    const { user } = setup();
    await user.type(screen.getByRole("combobox"), "at");
    await new Promise((resolve) => setTimeout(resolve, 250));
    expect(searchCards).not.toHaveBeenCalled();
  });

  it("queries once the term is long enough", async () => {
    const { user } = setup();
    await typeAndWait(user, "atl");
    expect(searchCards).toHaveBeenCalled();
  });

  it("debounces a burst of typing into one query", async () => {
    const { user } = setup();
    await typeAndWait(user, "atlas");
    // Five characters, one request — not three (one per keystroke past the minimum).
    expect(searchCards).toHaveBeenCalledTimes(1);
  });

  it("reports an empty result calmly", async () => {
    // Somebody pasting a 40-character string has not done anything wrong.
    searchCards.mockResolvedValue(page([]));
    const { user } = setup();
    await user.type(screen.getByRole("combobox"), "zzzz");
    await waitFor(() => expect(screen.getByText(/No cards match/)).toBeInTheDocument());
  });

  it("survives a failed search without breaking the field", async () => {
    searchCards.mockRejectedValue(new Error("offline"));
    const { user, input } = setup();
    await user.type(input, "atlas");
    await waitFor(() => expect(searchCards).toHaveBeenCalled());
    expect(input).toHaveFocus();
  });
});

describe("type → arrow → Enter", () => {
  it("adds the highlighted card, clears the field and refocuses", async () => {
    // The whole contract in one assertion. If the field is not cleared and refocused, the next
    // card needs a mouse and the ten-minute target is gone.
    const { user, input } = setup();
    await typeAndWait(user, "atl");

    await user.keyboard("{ArrowDown}");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(add).toHaveBeenCalledTimes(1));
    expect(add.mock.calls[0][0]).toMatchObject({
      printingId: "p2",
      label: { name: "Atlasborn", setCode: "FE01", collectorNumber: "BS1-002", finish: "normal" },
    });
    expect(input).toHaveValue("");
    expect(input).toHaveFocus();
    expect(screen.queryAllByRole("option")).toHaveLength(0);
  });

  it("Enter without moving takes the first row", async () => {
    // The first row is active from the moment results arrive, so Enter is immediately safe.
    const { user } = setup();
    await typeAndWait(user, "atl");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(add).toHaveBeenCalled());
    expect(add.mock.calls[0][0].printingId).toBe("p1");
  });

  it("moves the highlight up and down", async () => {
    const { user } = setup();
    await typeAndWait(user, "atl");

    await user.keyboard("{ArrowDown}");
    await waitFor(() =>
      expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true"),
    );
    await user.keyboard("{ArrowUp}");
    await waitFor(() =>
      expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true"),
    );
  });

  it("clamps at both ends rather than wrapping", async () => {
    // Wrapping is how somebody adds the wrong card while looking at the cards, not the screen.
    const { user } = setup();
    await typeAndWait(user, "atl");

    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{ArrowDown}{ArrowDown}{ArrowDown}{ArrowDown}");
    expect(screen.getAllByRole("option")[2]).toHaveAttribute("aria-selected", "true");
  });

  it("Enter with nothing to add does nothing and keeps focus", async () => {
    // No error flash. An empty field and a keystroke is not a mistake worth interrupting for.
    const { user, input } = setup();
    await user.keyboard("{Enter}");

    expect(add).not.toHaveBeenCalled();
    expect(input).toHaveFocus();
  });

  it("refuses to add a card with no printings", async () => {
    // There is nothing to put in an inventory row. Adding the card rather than a printing would
    // be a write with no printing_id.
    const { user } = setup();
    await typeAndWait(user, "atl");
    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(add).not.toHaveBeenCalled();
  });

  it("waits for an in-flight search instead of adding the previous result", async () => {
    // **The one that matters.** Type, results arrive, keep typing, press Enter before the second
    // search lands: acting on what is on screen adds the wrong card, silently, at speed. A visible
    // pause is the lesser failure by a wide margin.
    const { user, input } = setup();
    await typeAndWait(user, "atl");

    let release: (value: unknown) => void = () => {};
    searchCards.mockReturnValue(new Promise((resolve) => { release = resolve; }));

    await user.type(input, "as");
    await waitFor(() => expect(searchCards).toHaveBeenCalledTimes(2));

    await user.keyboard("{Enter}");
    expect(add).not.toHaveBeenCalled(); // still waiting, deliberately

    release(page([LATE_ARRIVAL, ATLASBORN]));

    await waitFor(() => expect(add).toHaveBeenCalledTimes(1));
    // The first row of the NEW result set. `p1` was on screen when Enter was pressed, and adding
    // it is the silent wrong-card bug this behaviour exists to prevent.
    expect(add.mock.calls[0][0].printingId).toBe("p9");
    expect(add.mock.calls[0][0].label.name).toBe("Atlas Shard");
  });
});

describe("Escape and Ctrl+Z", () => {
  it("Escape clears the term and keeps focus for the next card", async () => {
    const { user, input } = setup();
    await typeAndWait(user, "atl");

    await user.keyboard("{Escape}");
    expect(input).toHaveValue("");
    expect(input).toHaveFocus();
    expect(screen.queryAllByRole("option")).toHaveLength(0);
  });

  it("Ctrl+Z undoes the last add when the field is empty", async () => {
    const { user } = setup();
    await user.keyboard("{Control>}z{/Control}");
    expect(undoLast).toHaveBeenCalledTimes(1);
  });

  it("Cmd+Z works too", async () => {
    const { user } = setup();
    await user.keyboard("{Meta>}z{/Meta}");
    expect(undoLast).toHaveBeenCalledTimes(1);
  });

  it("Ctrl+Z leaves the browser's text undo alone while there is a term", async () => {
    // Somebody correcting a typo must not have their last add silently reversed instead.
    const { user, input } = setup();
    await user.type(input, "atl");
    await user.keyboard("{Control>}z{/Control}");

    expect(undoLast).not.toHaveBeenCalled();
  });
});

describe("assistive technology", () => {
  it("points aria-activedescendant at the highlighted option", async () => {
    const { user, input } = setup();
    await typeAndWait(user, "atl");

    await waitFor(() => expect(input).toHaveAttribute("aria-activedescendant"));
    await user.keyboard("{ArrowDown}");

    await waitFor(() => {
      const active = input.getAttribute("aria-activedescendant");
      expect(active).toBeTruthy();
      expect(document.getElementById(active!)).toHaveAttribute("aria-selected", "true");
    });
  });

  it("marks the field expanded only while there are results", async () => {
    const { user, input } = setup();
    expect(input).toHaveAttribute("aria-expanded", "false");

    await typeAndWait(user, "atl");
    expect(input).toHaveAttribute("aria-expanded", "true");

    await user.keyboard("{Escape}");
    await waitFor(() => expect(input).toHaveAttribute("aria-expanded", "false"));
  });
});
