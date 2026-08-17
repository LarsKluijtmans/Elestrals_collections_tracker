/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server runs on http://localhost:5173. The redirect URI you register on the login client
// (and the project's allowed origin) must match this origin — change both together if you move it.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  test: {
    // happy-dom rather than jsdom: jsdom's CSS colour chain (`cssstyle` →
    // `@asamuzakjp/css-color`) `require()`s an ESM-only module, which throws
    // ERR_REQUIRE_ESM before a single test runs, under either worker pool.
    environment: "happy-dom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // Components only. The API contract is tested against the real FastAPI app in
    // backend/tests; mocking it here as well would only assert that the mock matches itself.
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "text-summary"],
      // Scoped to the code that carries rules, not the whole app. A coverage number averaged
      // over page shells and generated locale files says nothing about whether the rules a
      // collection depends on are exercised — which is the question the threshold is asking.
      //
      // `src/collection/**` was missing until 2026-08-18, and its absence — not the scoping — is
      // what this comment should warn about. Bolt 006 put real rules there: the filter
      // vocabulary, the CSV contract, and the type-to-confirm gate on a bulk delete. Because the
      // list was never extended, the threshold silently stopped covering the newest rules in the
      // app while still printing "All files 95%" over 282 statements. A scope that is not
      // maintained becomes a scope that flatters.
      //
      // **When a directory starts carrying rules, add it here in the same commit.**
      include: ["src/session/**", "src/components/add/**", "src/collection/**"],
      // The three table components are presentation over `filters.ts` and the API types: no
      // branching a wrong answer could hide in, and covering them means asserting MUI renders a
      // table. `BulkBar` is deliberately *not* excluded — it holds the delete gate.
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/collection/CollectionTable.tsx",
        "src/collection/FilterRail.tsx",
      ],
      thresholds: { lines: 80, functions: 80, branches: 80, statements: 80 },
    },
  },
});
