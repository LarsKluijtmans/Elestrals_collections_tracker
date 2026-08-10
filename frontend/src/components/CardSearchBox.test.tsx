/**
 * The keyboard contract bolt 005 consumes.
 *
 * ux-guide §12: three characters → arrow → Enter, under five seconds, hands never leaving the
 * keyboard. If this drifts, the fast-add flow silently commits the wrong card — so it is
 * pinned here, in the bolt that defines it, rather than discovered two bolts later.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CardSearchResult } from "../api/backend";
import { CardSearchBox } from "./CardSearchBox";

const results: CardSearchResult[] = [
  {
    card_id: "c1", name: "Atlas", set_code: "FE01", collector_number: "BS1-001",
    card_type: "elestral", element: "earth", printing_count: 1, match_kind: "exact_name",
    primary_printing: {
      printing_id: "p1", rarity: "rare", finish: "normal", language: "en",
      edition: "first", image_url: null, alt_text: "Atlas — FE01 rare",
    },
  },
  {
    card_id: "c2", name: "Atlasborn", set_code: "FE01", collector_number: "BS1-002",
    card_type: "elestral", element: "fire", printing_count: 2, match_kind: "name_prefix",
    primary_printing: {
      printing_id: "p2", rarity: "common", finish: "normal", language: "en",
      edition: "first", image_url: null, alt_text: "Atlasborn — FE01 common",
    },
  },
  {
    card_id: "c3", name: "Teratlas", set_code: "FE01", collector_number: "BS1-003",
    card_type: "elestral", element: "water", printing_count: 1, match_kind: "infix",
    primary_printing: null,
  },
];

const searchCards = vi.hoisted(() => vi.fn());
vi.mock("../api/backend", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/backend")>()),
  searchCards: searchCards,
}));

function setup(onSelect = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <CardSearchBox onSelect={onSelect} />
    </QueryClientProvider>,
  );
  return { onSelect, user: userEvent.setup() };
}

async function typeAndWait(user: ReturnType<typeof userEvent.setup>, term: string) {
  await user.type(screen.getByRole("combobox"), term);
  await waitFor(() => expect(screen.getByRole("listbox")).toBeInTheDocument());
  await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(results.length));
}

beforeEach(() => {
  searchCards.mockResolvedValue({ items: results, next_cursor: null, total: results.length });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("CardSearchBox keyboard contract", () => {
  it("does not query below the minimum term length", async () => {
    const { user } = setup();
    await user.type(screen.getByRole("combobox"), "a");
    await new Promise((r) => setTimeout(r, 250));
    expect(searchCards).not.toHaveBeenCalled();
  });

  it("queries once the term is long enough", async () => {
    const { user } = setup();
    await typeAndWait(user, "atlas");
    expect(searchCards).toHaveBeenCalled();
  });

  it("activates the first row so Enter is immediately safe", async () => {
    const { user } = setup();
    await typeAndWait(user, "atlas");
    await waitFor(() =>
      expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true"),
    );
  });

  it("moves the active row with arrow keys", async () => {
    const { user } = setup();
    await typeAndWait(user, "atlas");

    await user.keyboard("{ArrowDown}");
    await waitFor(() =>
      expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true"),
    );

    await user.keyboard("{ArrowUp}");
    await waitFor(() =>
      expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true"),
    );
  });

  it("clamps at the ends instead of wrapping", async () => {
    // Wrapping is how someone adds the wrong card while looking at the keyboard, not the screen.
    const { user } = setup();
    await typeAndWait(user, "atlas");

    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{ArrowDown}{ArrowDown}{ArrowDown}{ArrowDown}");
    const options = screen.getAllByRole("option");
    expect(options[options.length - 1]).toHaveAttribute("aria-selected", "true");
  });

  it("selects the active row with Enter", async () => {
    const { user, onSelect } = setup();
    await typeAndWait(user, "atlas");

    await user.keyboard("{ArrowDown}");
    await user.keyboard("{Enter}");

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0][0].card_id).toBe("c2");
  });

  it("Enter with no movement selects the first row", async () => {
    const { user, onSelect } = setup();
    await typeAndWait(user, "atlas");

    await user.keyboard("{Enter}");
    expect(onSelect.mock.calls[0][0].card_id).toBe("c1");
  });

  it("Escape clears the term and keeps focus for the next card", async () => {
    const { user } = setup();
    await typeAndWait(user, "atlas");

    await user.keyboard("{Escape}");
    const input = screen.getByRole("combobox");
    expect(input).toHaveValue("");
    expect(input).toHaveFocus();
  });

  it("exposes the active row to assistive technology", async () => {
    const { user } = setup();
    await typeAndWait(user, "atlas");

    const input = screen.getByRole("combobox");
    await waitFor(() => expect(input).toHaveAttribute("aria-activedescendant"));

    await user.keyboard("{ArrowDown}");
    await waitFor(() => {
      const active = input.getAttribute("aria-activedescendant");
      expect(active).toBeTruthy();
      expect(document.getElementById(active!)).toHaveAttribute("aria-selected", "true");
    });
  });

  it("renders the element name, never colour alone", async () => {
    const { user } = setup();
    await typeAndWait(user, "atlas");
    expect(screen.getByText("Earth")).toBeInTheDocument();
    expect(screen.getByText("Fire")).toBeInTheDocument();
  });

  it("tolerates a result with no printings", async () => {
    const { user, onSelect } = setup();
    await typeAndWait(user, "atlas");

    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
    expect(onSelect.mock.calls[0][0].card_id).toBe("c3");
  });

  it("reports when nothing matched", async () => {
    searchCards.mockResolvedValue({ items: [], next_cursor: null, total: 0 });
    const { user } = setup();
    await user.type(screen.getByRole("combobox"), "zzzz");
    await waitFor(() => expect(screen.getByText("No cards found")).toBeInTheDocument());
  });
});
