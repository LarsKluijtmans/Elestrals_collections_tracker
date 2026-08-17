/**
 * Bulk actions — story 022, and the two rules that make a 500-row delete survivable.
 *
 * **Type-to-confirm above 20.** Bolt 006 records this criterion as met, and until this file it had
 * no test: `test_bulk_actions.py` proves the *server* applies a bulk delete, but the rule that
 * stops a collector deleting 1,247 cards by reflex lives only here. A criterion whose only
 * evidence is a rendered component nobody renders in a test is a criterion nobody checked.
 *
 * **Partial failure is named, not summarised away.** A collector who knows 12 of 500 rows failed
 * but not *which* has an unknown collection, which is worse than a failed operation.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { BulkResult } from "../api/backend";
import { BulkBar } from "./BulkBar";

function setup(overrides: Partial<Parameters<typeof BulkBar>[0]> = {}) {
  const props = {
    count: 5,
    busy: false,
    result: null as BulkResult | null,
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onExport: vi.fn(),
    onClear: vi.fn(),
    onDismissResult: vi.fn(),
    ...overrides,
  };
  render(<BulkBar {...props} />);
  return { ...props, user: userEvent.setup() };
}

/**
 * The open dialog, and only the open one.
 *
 * Both this and the toolbar have a button called "Delete", so an unscoped
 * `getByRole("button", { name: "Delete" })` is ambiguous by *meaning* even when it is unambiguous
 * by count — and the count flips around during MUI's transitions, because while a modal is open
 * MUI marks the app root `aria-hidden` and role queries skip hidden subtrees. So mid-transition
 * the toolbar button is the invisible one and the dialog's is what you get.
 *
 * That is not hypothetical: the reopen test below clicked the dialog's confirm button believing it
 * was the toolbar's, and *confirmed a delete* while claiming to reopen the dialog. Naming which
 * one you mean is what stops a green test from exercising a different path than it describes.
 */
const dialog = () => within(screen.getByRole("dialog"));

/** The confirm button *inside* the dialog, not the toolbar button that opened it. */
const deleteButton = () => dialog().getByRole("button", { name: "Delete" });

describe("type-to-confirm", () => {
  it("deletes on one click at or below the threshold", async () => {
    // An ordinary tidy-up must not need ceremony, or the ceremony stops being read.
    const { user, onDelete } = setup({ count: 20 });
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(dialog().queryByLabelText(/Type 20 to confirm/)).not.toBeInTheDocument();
    await user.click(deleteButton());
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("demands the typed count above the threshold", async () => {
    const { user, onDelete } = setup({ count: 21 });
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(dialog().getByLabelText(/Type 21 to confirm/)).toBeInTheDocument();
    // Asserted as disabled rather than clicked: user-event refuses to click through
    // `pointer-events: none`, which is the correct behaviour to assert against anyway — a real
    // pointer cannot reach it either.
    expect(deleteButton()).toBeDisabled();
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("stays disabled for a wrong number", async () => {
    // The near-miss is the case that matters: 124 typed for 1,247 must not delete 1,247.
    const { user } = setup({ count: 1247 });
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.type(dialog().getByLabelText(/Type 1247 to confirm/), "124");

    expect(deleteButton()).toBeDisabled();
  });

  it("enables once the exact count is typed", async () => {
    const { user, onDelete } = setup({ count: 1247 });
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.type(dialog().getByLabelText(/Type 1247 to confirm/), "1247");

    expect(deleteButton()).toBeEnabled();
    await user.click(deleteButton());
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("accepts the count with surrounding whitespace", async () => {
    // Typed into a text field by someone reading it off the dialog; a trailing space is not a
    // different intention.
    const { user, onDelete } = setup({ count: 30 });
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.type(dialog().getByLabelText(/Type 30 to confirm/), " 30 ");

    await user.click(deleteButton());
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("does not accept the grouped rendering of the number", async () => {
    // The dialog title says "1,247 cards" but the field asks for `1247`. Worth pinning: if the
    // label and the comparison ever disagree, the gate becomes unpassable rather than lax.
    const { user } = setup({ count: 1247 });
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.type(dialog().getByLabelText(/Type 1247 to confirm/), (1247).toLocaleString());

    expect(deleteButton()).toBeDisabled();
  });

  it("clears a previous entry when the dialog is reopened", async () => {
    // Otherwise a typed confirmation from a 30-row delete would still be sitting there for the
    // next one, and the gate would be open before it was read.
    const { user } = setup({ count: 30 });
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.type(dialog().getByLabelText(/Type 30 to confirm/), "30");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    // Wait for the dialog to actually leave. While its exit transition runs, MUI still has the
    // app root `aria-hidden`, so the *toolbar* Delete is invisible to role queries and
    // `getByRole` resolves to the dialog's own Delete instead — clicking which confirms the
    // delete rather than reopening the dialog. Without this wait the test passes through a
    // completely different path from the one it claims to exercise.
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Delete" }));

    // The gate being shut again is the rule; the empty field is how it is shut.
    //
    // `.value` directly rather than `toHaveValue("")`: jest-dom special-cases the empty string and
    // fails the match even when the input really is empty, printing a blank expected *and* a blank
    // received — which reads as a mystery rather than as the quirk it is.
    expect((dialog().getByRole("textbox") as HTMLInputElement).value).toBe("");
    expect(deleteButton()).toBeDisabled();
  });
});

describe("the confirmation names the count", () => {
  it("puts the number in the dialog, not just 'these'", async () => {
    const { user } = setup({ count: 1247 });
    await user.click(screen.getByRole("button", { name: "Delete" }));

    // textContent rather than getByText: React splits `Delete {n} cards?` into three text
    // nodes, so no single node holds the sentence. And the separator comes from
    // `toLocaleString()`, which is "." here and "," under en-US — asserting either literal
    // would make this test pass or fail on the machine's locale rather than on the code.
    expect(screen.getByRole("dialog").textContent)
      .toContain(`Delete ${(1247).toLocaleString()} cards?`);
  });

  it("says row rather than rows for a single card", async () => {
    const { user } = setup({ count: 1 });
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(screen.getByRole("dialog").textContent).toContain("1 row from your collection");
  });
});

describe("partial failure", () => {
  function result(failures: number, applied = 500): BulkResult {
    return {
      requested: 500,
      applied,
      failures: Array.from({ length: failures }, (_, i) => ({
        item_id: `abcdef${String(i).padStart(4, "0")}-rest-of-the-uuid`,
        reason: `row ${i} was gone`,
      })),
    } as BulkResult;
  }

  it("names each failed row", () => {
    setup({ count: 0, result: result(3, 497) });

    expect(screen.getByText(/497 of 500 applied, 3 failed/)).toBeInTheDocument();
    expect(screen.getByText(/row 0 was gone/)).toBeInTheDocument();
    expect(screen.getByText(/row 2 was gone/)).toBeInTheDocument();
  });

  it("caps the list and says how many more", () => {
    // The alternative is a 500-item list nobody scrolls, which hides the failures just as well.
    setup({ count: 0, result: result(12, 488) });

    expect(screen.getByText(/…and 2 more/)).toBeInTheDocument();
  });

  it("reports a clean run as a success rather than a warning", () => {
    setup({ count: 0, result: result(0) });

    expect(screen.getByText(/500 of 500 applied\./)).toBeInTheDocument();
    expect(screen.queryByText(/failed/)).not.toBeInTheDocument();
  });

  it("survives being dismissed", async () => {
    const { user, onDismissResult } = setup({ count: 0, result: result(1, 499) });
    await user.click(screen.getByRole("button", { name: /close/i }));

    expect(onDismissResult).toHaveBeenCalledOnce();
  });
});

describe("the edit dialog", () => {
  it("sends undefined for a field left blank, not an empty string", async () => {
    // "Leave unchanged" and "set to empty" are different operations, and conflating them would
    // wipe storage locations somebody spent an evening entering.
    const { user, onEdit } = setup({ count: 4 });
    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: /Apply to 4/ }));

    expect(onEdit).toHaveBeenCalledWith({
      condition: undefined,
      storage_location: undefined,
      is_for_trade: undefined,
    });
  });

  it("sends false for an explicit no rather than dropping it", async () => {
    // `is_for_trade: false` is a real edit. A truthiness check would silently turn it into
    // "leave unchanged", so the one edit that unsets the flag would do nothing.
    const { user, onEdit } = setup({ count: 4 });
    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("combobox", { name: "For trade" }));
    await user.click(screen.getByRole("option", { name: "No" }));
    await user.click(screen.getByRole("button", { name: /Apply to 4/ }));

    expect(onEdit).toHaveBeenCalledWith(
      expect.objectContaining({ is_for_trade: false }),
    );
  });
});

describe("rendering", () => {
  it("renders nothing with no selection and no result", () => {
    const { container } = render(
      <BulkBar
        count={0} busy={false} result={null}
        onEdit={vi.fn()} onDelete={vi.fn()} onExport={vi.fn()}
        onClear={vi.fn()} onDismissResult={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("announces the selection count politely", () => {
    // The count changes as rows are ticked; a screen reader user needs it without hunting.
    setup({ count: 42 });
    expect(screen.getByText("42 selected")).toHaveAttribute("aria-live", "polite");
  });

  it("disables the actions while a bulk request is in flight", () => {
    setup({ count: 5, busy: true });

    expect(screen.getByRole("button", { name: "Edit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Export" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
  });

  it("leaves clear-selection available while busy", () => {
    // Backing out of a slow operation is the one thing that must stay possible.
    setup({ count: 5, busy: true });
    expect(screen.getByRole("button", { name: "Clear selection" })).toBeEnabled();
  });
});
