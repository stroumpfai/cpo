import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8002",
    },
  },
  build: {
    outDir: "../backend/dist",
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    passWithNoTests: true,
    // Exclude Playwright E2E tests — they run via `npx playwright test`, not Vitest
    exclude: ['e2e/**', 'node_modules/**'],
  },
});
