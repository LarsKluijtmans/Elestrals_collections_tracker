/**
 * The most-used control in the product — story 019, and its numbers are requirements.
 *
 * `test_holding_the_button_sends_one_request` is the load-bearing one: without the debounce, a
 * held `+` fires twenty row-level writes that race each other, and the row ends on whichever one
 * happens to land last.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DEBOUNCE_MS, QuantityStepper } from "./QuantityStepper";

function setup(props: Partial<Parameters<typeof QuantityStepper>[0]> = {}) {
  const onChange = vi.fn();
  const view = render(
    <QuantityStepper value={props.value ?? 1} label="Atlas" onChange={onChange} {...props} />,
  );
  return { onChange, user: userEvent.setup(), view };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, DEBOUNCE_MS + 100));

afterEach(() => {
  vi.clearAllMocks();
});

describe("the controls", () => {
  it("names both buttons for a screen reader", () => {
    // "+" and "−" are meaningless read aloud, and this row is one of hundreds.
    setup();
    expect(screen.getByRole("button", { name: "Add one Atlas" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove one Atlas" })).toBeInTheDocument();
  });

  it("announces the count with the card it belongs to", () => {
    setup({ value: 3 });
    expect(screen.getByLabelText("3 copies of Atlas")).toBeInTheDocument();
  });

  it("cannot go below the floor", () => {
    // One is the floor, not zero: a zero-quantity row is a deletion that did not happen, and
    // bolt 004 enforces that with a CHECK constraint.
    setup({ value: 1 });
    expect(screen.getByRole("button", { name: "Remove one Atlas" })).toBeDisabled();
  });

  it("cannot go above the ceiling", () => {
    setup({ value: 10_000 });
    expect(screen.getByRole("button", { name: "Add one Atlas" })).toBeDisabled();
  });
});

describe("optimism", () => {
  it("moves the number on the click, not on the response", async () => {
    const { user } = setup({ value: 2 });
    await user.click(screen.getByRole("button", { name: "Add one Atlas" }));

    // Immediately, before any debounce has elapsed and long before a request could return.
    expect(screen.getByLabelText("3 copies of Atlas")).toBeInTheDocument();
  });
});

describe("debouncing", () => {
  it("holding the button sends one request for the net change", async () => {
    /** **The one that matters.** Five presses without this is five concurrent writes to one row,
     *  each carrying a different expectation, and the winner is whichever lands last. */
    const { user, onChange } = setup({ value: 1 });
    const plus = screen.getByRole("button", { name: "Add one Atlas" });

    await user.click(plus);
    await user.click(plus);
    await user.click(plus);
    await user.click(plus);
    await user.click(plus);

    await waitFor(() => expect(onChange).toHaveBeenCalled(), { timeout: 2000 });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(6);
  });

  it("a burst up and back down cancels out to no request", async () => {
    const { user, onChange } = setup({ value: 3 });
    await user.click(screen.getByRole("button", { name: "Add one Atlas" }));
    await user.click(screen.getByRole("button", { name: "Remove one Atlas" }));

    await settle();
    // Net zero. Sending `3` to set it to what it already is would be a pointless write and a
    // pointless entry in whatever audit trail eventually watches this table.
    expect(onChange).not.toHaveBeenCalled();
  });

  it("two separate changes send two requests", async () => {
    const { user, onChange } = setup({ value: 1 });
    await user.click(screen.getByRole("button", { name: "Add one Atlas" }));
    await settle();
    await user.click(screen.getByRole("button", { name: "Add one Atlas" }));
    await settle();

    expect(onChange).toHaveBeenCalledTimes(2);
    expect(onChange).toHaveBeenLastCalledWith(3);
  });
});

describe("reconciling with the server", () => {
  it("takes a new value from elsewhere while idle", async () => {
    // A bulk edit, another tab, a refetch. The row is not the only writer.
    const { view } = setup({ value: 2 });
    view.rerender(<QuantityStepper value={7} label="Atlas" onChange={vi.fn()} />);
    expect(screen.getByLabelText("7 copies of Atlas")).toBeInTheDocument();
  });

  it("does not yank the number back mid-hold", async () => {
    /** A refetch landing between a click and its debounced request would otherwise reset the
     *  display under the user's finger — which reads as the button not working. */
    const onChange = vi.fn();
    const view = render(<QuantityStepper value={2} label="Atlas" onChange={onChange} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Add one Atlas" }));
    view.rerender(<QuantityStepper value={2} label="Atlas" onChange={onChange} />);

    expect(screen.getByLabelText("3 copies of Atlas")).toBeInTheDocument();
  });
});
