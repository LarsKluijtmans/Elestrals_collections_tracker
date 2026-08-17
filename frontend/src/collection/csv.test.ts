/**
 * The CSV shape — shared by story 022's selection export, story 024's missing list and story 027's
 * full export.
 *
 * The escaping tests are not pedantry. Card names contain commas and apostrophes, at least one set
 * has a quote in a name, and a file that breaks on any of them produces a *silently wrong* import
 * rather than a failed one — rows shifted a column to the right parse fine and mean something else.
 */
import { describe, expect, it } from "vitest";
import { COLUMNS, escapeField, toCsv } from "./csv";

describe("escaping", () => {
  it("leaves a plain value alone", () => {
    expect(escapeField("Atlas")).toBe("Atlas");
  });

  it("quotes a value containing a comma", () => {
    // The one that shifts every later column by one if it is missed.
    expect(escapeField("Atlas, Reborn")).toBe('"Atlas, Reborn"');
  });

  it("doubles an embedded quote", () => {
    expect(escapeField('The "Real" Atlas')).toBe('"The ""Real"" Atlas"');
  });

  it("quotes a value containing a newline", () => {
    expect(escapeField("Atlas\nReborn")).toBe('"Atlas\nReborn"');
  });

  it("renders null and undefined as empty, not as the word", () => {
    // `"None"` and `"undefined"` are the classic ones, and they import as real strings.
    expect(escapeField(null)).toBe("");
    expect(escapeField(undefined)).toBe("");
  });

  it("renders booleans as true/false rather than 1/0", () => {
    expect(escapeField(true)).toBe("true");
    expect(escapeField(false)).toBe("false");
  });

  it("renders zero as 0, not as empty", () => {
    // `if (!value)` would blank it, and a quantity column of empties is a broken import.
    expect(escapeField(0)).toBe("0");
  });
});

describe("toCsv", () => {
  it("writes the importer's header in the importer's order", () => {
    // The column order is the import contract. Two orders means an export you cannot re-import,
    // which kills the export-edit-import workflow all three stories exist to serve.
    const [header] = toCsv([]).split("\r\n");
    expect(header).toBe(COLUMNS.join(","));
  });

  it("writes one line per row", () => {
    const csv = toCsv([
      { set_code: "FE01", collector_number: "BS1-001", name: "Atlas", quantity: 2 },
      { set_code: "FE01", collector_number: "BS1-002", name: "Vipyro", quantity: 1 },
    ]);
    expect(csv.trimEnd().split("\r\n")).toHaveLength(3);
  });

  it("leaves an absent column empty rather than shifting the row", () => {
    const [, row] = toCsv([{ set_code: "FE01", name: "Atlas" }]).split("\r\n");
    const cells = row.split(",");
    expect(cells).toHaveLength(COLUMNS.length);
    expect(cells[0]).toBe("FE01");
    expect(cells[1]).toBe("");          // collector_number
    expect(cells[2]).toBe("Atlas");
  });

  it("uses CRLF line endings", () => {
    // RFC 4180, and Excel on Windows — the most likely destination — renders LF-only CSV as one
    // very long line.
    expect(toCsv([{ name: "Atlas" }])).toContain("\r\n");
  });

  it("ends with a newline", () => {
    expect(toCsv([{ name: "Atlas" }]).endsWith("\r\n")).toBe(true);
  });

  it("escapes inside a full row", () => {
    const csv = toCsv([{ name: 'Atlas, "Reborn"', set_code: "FE01" }]);
    expect(csv).toContain('"Atlas, ""Reborn"""');
  });
});
