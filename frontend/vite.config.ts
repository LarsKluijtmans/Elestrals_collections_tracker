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
  },
});
