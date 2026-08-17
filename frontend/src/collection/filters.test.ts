/**
 * The filter serialisation — story 020.
 *
 * The URL *is* the state here, so the round-trip is not a nicety: it is what makes a filtered
 * collection shareable and the back button work. Story 020's note says retrofitting this later
 * means rewriting every filter component, which is why it is pinned before any of them exist.
 */
import { describe, expect, it } from "vitest";
import {
  activeFilterCount,
  cycleTristate,
  describeFilters,
  parseFilters,
  toSearchParams,
  toggleValue,
  type Filters,
} from "./filters";

const parse = (query: string) => parseFilters(new URLSearchParams(query));
const serialise = (filters: Filters) => toSearchParams(filters).toString();

describe("parsing a URL", () => {
  it("reads nothing out of an empty query", () => {
    expect(parse("")).toEqual({});
  });

  it("reads repeated parameters as an OR within the attribute", () => {
    expect(parse("element=fire&element=water")).toEqual({ element: ["fire", "water"] });
  });

  it("reads several attributes as an AND across them", () => {
    expect(parse("element=fire&condition=near_mint")).toEqual({
      element: ["fire"], condition: ["near_mint"],
    });
  });

  it("reads all three states of a tri-state flag", () => {
    expect(parse("").is_graded).toBeUndefined();
    expect(parse("is_graded=true").is_graded).toBe(true);
    expect(parse("is_graded=false").is_graded).toBe(false);
  });

  it("ignores a nonsense tri-state rather than guessing", () => {
    // A hand-edited URL should not silently become "graded only".
    expect(parse("is_graded=maybe").is_graded).toBeUndefined();
  });

  it("drops empty values from a cleared select", () => {
    expect(parse("element=&element=fire")).toEqual({ element: ["fire"] });
  });

  it("ignores parameters it does not know", () => {
    // A shared link carrying `?utm_source=` must still open the right view.
    expect(parse("element=fire&utm_source=twitter")).toEqual({ element: ["fire"] });
  });
});

describe("round-tripping", () => {
  it("survives every attribute", () => {
    const original: Filters = {
      set_code: ["FE01", "FE02"],
      element: ["fire"],
      rarity: ["holo_rare"],
      condition: ["near_mint", "mint"],
      finish: ["foil"],
      language: ["en"],
      is_graded: false,
      is_for_trade: true,
      q: "atlas",
    };

    expect(parse(serialise(original))).toEqual(original);
  });

  it("keeps a tri-state false", () => {
    // The one a naive `if (value)` serialiser loses. `is_graded=false` means "ungraded only";
    // dropping it because it is falsy turns that view into "everything".
    expect(serialise({ is_graded: false })).toBe("is_graded=false");
    expect(parse(serialise({ is_graded: false })).is_graded).toBe(false);
  });

  it("leaves the default sort out of the URL", () => {
    // So the canonical link for an unfiltered collection is `/collection`, not
    // `/collection?sort=added_desc` — two URLs for one view is how a shared link looks wrong.
    expect(toSearchParams({}, { sort: "added_desc" }).toString()).toBe("");
    expect(toSearchParams({}, { sort: "name_asc" }).toString()).toBe("sort=name_asc");
  });

  it("carries a cursor when there is one", () => {
    expect(toSearchParams({}, { cursor: "abc" }).get("cursor")).toBe("abc");
  });
});

describe("counting what is active", () => {
  it("is zero for an empty filter", () => {
    expect(activeFilterCount({})).toBe(0);
  });

  it("counts an attribute once however many values it has", () => {
    expect(activeFilterCount({ element: ["fire", "water", "earth"] })).toBe(1);
  });

  it("counts a tri-state false as active", () => {
    expect(activeFilterCount({ is_graded: false })).toBe(1);
  });

  it("counts a search term", () => {
    expect(activeFilterCount({ q: "atlas", element: ["fire"] })).toBe(2);
  });
});

describe("describing what is active", () => {
  it("names the filters, so an empty result can say what to loosen", () => {
    // "No results" is indistinguishable from an empty collection, which is a different fact.
    const described = describeFilters({ element: ["fire"], condition: ["near_mint"] });
    expect(described).toBe("Fire, Near Mint");
  });

  it("joins several values of one attribute with 'or'", () => {
    expect(describeFilters({ element: ["fire", "water"] })).toBe("Fire or Water");
  });

  it("spells out both sides of a tri-state", () => {
    expect(describeFilters({ is_graded: true })).toBe("graded");
    expect(describeFilters({ is_graded: false })).toBe("ungraded");
  });
});

describe("toggling", () => {
  it("adds a value that was not there", () => {
    expect(toggleValue({}, "element", "fire")).toEqual({ element: ["fire"] });
  });

  it("removes a value that was", () => {
    expect(toggleValue({ element: ["fire", "water"] }, "element", "fire"))
      .toEqual({ element: ["water"] });
  });

  it("drops the attribute entirely when its last value goes", () => {
    // Otherwise the URL keeps an empty `element=` and the filter reads as active when it is not.
    expect(toggleValue({ element: ["fire"] }, "element", "fire")).toEqual({});
  });

  it("does not mutate the input", () => {
    const original: Filters = { element: ["fire"] };
    toggleValue(original, "element", "water");
    expect(original).toEqual({ element: ["fire"] });
  });
});

describe("cycling a tri-state", () => {
  it("goes unset → true → false → unset", () => {
    let filters: Filters = {};
    filters = cycleTristate(filters, "is_graded");
    expect(filters.is_graded).toBe(true);
    filters = cycleTristate(filters, "is_graded");
    expect(filters.is_graded).toBe(false);
    filters = cycleTristate(filters, "is_graded");
    // The third click clears it — how a user gets back to "either" without hunting for a reset.
    expect(filters.is_graded).toBeUndefined();
  });
});
