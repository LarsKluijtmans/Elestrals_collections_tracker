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

/**
 * Escape one field.
 *
 * A card called `Atlas, Reborn` breaks a naive join on commas — and card names contain commas,
 * quotes and, in at least one set, a newline in the flavour line. RFC 4180: wrap in quotes, double
 * any quote inside.
 */
export function escapeField(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return "";
  const text = typeof value === "boolean" ? (value ? "true" : "false") : String(value);
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
