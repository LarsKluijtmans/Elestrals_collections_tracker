import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server runs on http://localhost:5173. The redirect URI you register on the login client
// (and the project's allowed origin) must match this origin — change both together if you move it.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
