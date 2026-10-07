import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev, the frontend calls the backend through Vite's proxy, so the browser only
// ever talks to one origin (no CORS setup needed locally).
const backend = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // reachable from a phone on the same Wi-Fi, for demo checks
    proxy: {
      "/api": backend,
      "/health": backend,
    },
  },
});
