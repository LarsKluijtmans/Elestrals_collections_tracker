/**
 * Carry-forward — the single largest contributor to the five-second target.
 *
 * The bar works by being *ignorable*: set once, never looked at again. So the tests worth having
 * are the keyboard shortcuts (the flow is keyboard-only, and a picker that needs a mouse breaks it
 * for exactly the person entering two hundred cards) and the wrap at the end of each list.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CarriedDefaultsBar } from "./CarriedDefaultsBar";

const changeDefaults = vi.hoisted(() => vi.fn());
const carried = vi.hoisted(() => ({
  current: { condition: "near_mint", finish: "normal", language: "en", edition: "unlimited" },
}));

vi.mock("../../session/AddSessionContext", () => ({
  useAddSession: () => ({ carried: carried.current, changeDefaults }),
}));

function setup() {
  render(<CarriedDefaultsBar />);
  return { user: userEvent.setup() };
}

beforeEach(() => {
  carried.current = {
    condition: "near_mint", finish: "normal", language: "en", edition: "unlimited",
  };
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("what it shows", () => {
  it("shows the current condition and finish", () => {
    setup();
    expect(screen.getByLabelText("Condition")).toHaveTextContent("near mint");
    expect(screen.getByLabelText("Finish")).toHaveTextContent("normal");
  });

  it("says the settings carry forward, rather than leaving it to be discovered", () => {
    setup();
    expect(screen.getByText(/carry forward to every add/i)).toBeInTheDocument();
  });

  it("advertises both shortcuts", () => {
    setup();
    expect(screen.getByText("Alt+C")).toBeInTheDocument();
    expect(screen.getByText("Alt+F")).toBeInTheDocument();
  });
});

describe("changing them with the keyboard", () => {
  it("Alt+C moves to the next condition", async () => {
    const { user } = setup();
    await user.keyboard("{Alt>}c{/Alt}");
    expect(changeDefaults).toHaveBeenCalledWith({ condition: "lightly_played" });
  });

  it("Alt+F moves to the next finish", async () => {
    const { user } = setup();
    await user.keyboard("{Alt>}f{/Alt}");
    expect(changeDefaults).toHaveBeenCalledWith({ finish: "foil" });
  });

  it("wraps from the last option back to the first", async () => {
    // Otherwise Alt+C stops working once you reach Damaged, which reads as the shortcut breaking.
    carried.current = { ...carried.current, condition: "damaged", finish: "prismatic" };
    const { user } = setup();

    await user.keyboard("{Alt>}c{/Alt}");
    expect(changeDefaults).toHaveBeenCalledWith({ condition: "mint" });

    await user.keyboard("{Alt>}f{/Alt}");
    expect(changeDefaults).toHaveBeenCalledWith({ finish: "normal" });
  });

  it("ignores the same keys without Alt", async () => {
    // `c` and `f` are letters a collector types into the search field constantly.
    const { user } = setup();
    await user.keyboard("cf");
    expect(changeDefaults).not.toHaveBeenCalled();
  });

  it("ignores other Alt combinations", async () => {
    const { user } = setup();
    await user.keyboard("{Alt>}x{/Alt}");
    expect(changeDefaults).not.toHaveBeenCalled();
  });

  it("stops listening once it unmounts", async () => {
    // A stale window listener would keep changing a session the user has left.
    const view = render(<CarriedDefaultsBar />);
    const user = userEvent.setup();
    view.unmount();

    await user.keyboard("{Alt>}c{/Alt}");
    expect(changeDefaults).not.toHaveBeenCalled();
  });
});

describe("changing them with the mouse", () => {
  it("picking a condition carries it forward", async () => {
    const { user } = setup();
    await user.click(screen.getByLabelText("Condition"));
    await user.click(screen.getByRole("option", { name: "heavily played" }));

    expect(changeDefaults).toHaveBeenCalledWith({ condition: "heavily_played" });
  });

  it("picking a finish carries it forward", async () => {
    const { user } = setup();
    await user.click(screen.getByLabelText("Finish"));
    await user.click(screen.getByRole("option", { name: "reverse foil" }));

    expect(changeDefaults).toHaveBeenCalledWith({ finish: "reverse_foil" });
  });

  it("offers every condition the inventory model accepts", async () => {
    // A condition missing here is a condition a collector cannot record, and the six are the
    // scale bolt 004 stores.
    const { user } = setup();
    await user.click(screen.getByLabelText("Condition"));
    expect(screen.getAllByRole("option")).toHaveLength(6);
  });
});
