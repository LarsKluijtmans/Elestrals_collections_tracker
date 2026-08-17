// The CSV shape — one definition, three callers.
//
// Story 022 exports a selection, story 024 exports a missing list, and story 027 exports a whole
// collection. All three must produce a file **the importer accepts**, which story 024 states
// outright: an export you cannot re-import is a dead end, and "export, edit in a spreadsheet,
// re-import" is the workflow every one of these exists to serve.
//
// So the column order and header spellings live here, and nowhere else.

/** The importer's columns, in its order. Changing this changes the import contract. */
export const COLUMNS = [
  "set_code",
  "collector_number",
  "name",
  "rarity",
  "finish",
  "language",
  "edition",
  "condition",
  "quantity",
  "is_graded",
  "grader",
  "grade",
  "storage_location",
  "is_for_trade",
] as const;

export type CsvRow = Partial<Record<(typeof COLUMNS)[number], string | number | boolean | null>>;

/** The four characters a spreadsheet treats as the start of a formula. */
const FORMULA_PREFIXES = ["=", "+", "-", "@"];

/**
 * Defuse anything a spreadsheet would execute.
 *
 * The mirror of `neutralise()` in `backend/app/services/export_service.py`, and it exists here for
 * the same reason it exists there: the attack is on the **user**, not on us. A `storage_location`
 * somebody typed as `=IMPORTXML("http://…","//x")` is inert in our database and becomes a live
 * formula the moment they open the export in Excel — where it can read the rest of their sheet.
 *
 * This file had RFC 4180 quoting and nothing else, so the two export paths disagreed: the server
 * export was defused and the client export was not, for the same data. `storage_location` is
 * user-typed free text and `name` comes from the catalog importer, so both a user's own text and
 * ingested third-party text reach a spreadsheet through here.
 *
 * `'` is the prefix because Excel, Sheets and LibreOffice all strip it on display — the user sees
 * what they wrote and the cell is inert. Tab and CR are included because at least one of the three
 * treats them as formula-leading whitespace.
 */
export function neutralise(text: string): string {
  const first = text.slice(0, 1);
  return FORMULA_PREFIXES.includes(first) || first === "\t" || first === "\r" ? `'${text}` : text;
}

/**
 * Escape one field.
 *
 * A card called `Atlas, Reborn` breaks a naive join on commas — and card names contain commas,
 * quotes and, in at least one set, a newline in the flavour line. RFC 4180: wrap in quotes, double
 * any quote inside.
 *
 * Defusing happens **before** quoting, so a value that is both dangerous and comma-bearing gets the
 * `'` inside the quotes where the spreadsheet will honour it, rather than outside where it would
 * corrupt the field.
 */
export function escapeField(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return "";
  const raw = typeof value === "boolean" ? (value ? "true" : "false") : String(value);
  const text = neutralise(raw);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(rows: CsvRow[], columns: readonly string[] = COLUMNS): string {
  const header = columns.join(",");
  const body = rows.map((row) =>
    columns.map((column) => escapeField((row as Record<string, never>)[column])).join(","),
  );
  // CRLF, because RFC 4180 says so and because Excel on Windows — the single most likely
  // destination for this file — renders LF-only CSV as one long line.
  return [header, ...body].join("\r\n") + "\r\n";
}

export function downloadCsv(content: string, filename: string): void {
  // A BOM, so Excel reads the file as UTF-8 rather than as the system codepage. Without it a
  // card called "Pyrofrost Éclair" arrives as mojibake, which looks like our data being wrong.
  const blob = new Blob(["﻿", content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
