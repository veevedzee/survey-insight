import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the browser talks to Vite on :5173, and Vite forwards /api/*
// to FastAPI on :8000. Same origin for the browser = no CORS setup needed locally.
// In production VITE_API_URL points at the deployed backend instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
