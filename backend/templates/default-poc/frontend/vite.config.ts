import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Canonical Vite config shipped by the platform: every generated PoC builds
// the same way regardless of whether the AI produced its own config.
export default defineConfig({
  plugins: [react()],
});
