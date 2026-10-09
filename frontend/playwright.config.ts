import { defineConfig } from "@playwright/test";

// End-to-end tests drive the real app (built, with its service worker) against a real
// API on a freshly reset demo database (TEST_DATABASE_URL, fake embeddings for speed).
// Every test runs at phone width (375px) and laptop width (1280px).
// Let tests block the service worker's own network requests too (Chromium), so the
// offline tests really are offline. Without it, those requests sometimes slip through.
process.env.PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS ??= "1";

const API_PORT = 8011;
const WEB_PORT = 4183;
const testDb =
  process.env.TEST_DATABASE_URL ??
  "postgresql+psycopg://circuit:circuit@localhost:5432/circuit_test";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1, // one shared demo database
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "phone",
      use: { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
    },
    { name: "laptop", use: { viewport: { width: 1280, height: 800 } } },
  ],
  webServer: [
    {
      command: "uv run python -m app.cli reset-demo && uv run python -m app",
      cwd: "../backend",
      url: `http://localhost:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 180_000,
      env: {
        PORT: String(API_PORT),
        DATABASE_URL: testDb,
        ENV: "test",
        DEMO_AUTH: "true",
        EMBEDDING_PROVIDER: "fake",
        SCHEDULER_ENABLED: "false",
        ANTHROPIC_API_KEY: "",
        LOG_LEVEL: "WARNING",
      },
    },
    {
      command: `npm run build && npx vite preview --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}/welcome`,
      reuseExistingServer: false,
      timeout: 180_000,
      // VITE_DESIGN_PAGE: the /design component gallery is in the test build.
      env: { API_PROXY_TARGET: `http://localhost:${API_PORT}`, VITE_DESIGN_PAGE: "1" },
    },
  ],
});
