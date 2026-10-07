import { test as base } from "@playwright/test";
import { execSync } from "node:child_process";

const testDb =
  process.env.TEST_DATABASE_URL ??
  "postgresql+psycopg://circuit:circuit@localhost:5432/circuit_test";

/** Restore the demo seed (about 6 s), for tests that apply, shortlist or claim. */
export function resetDemo() {
  execSync("uv run python -m app.cli reset-demo", {
    cwd: "../backend",
    env: { ...process.env, DATABASE_URL: testDb, EMBEDDING_PROVIDER: "fake", ENV: "test" },
    stdio: "ignore",
  });
}

/** Every test runs without internet map tiles, so results don't depend on a third
 *  party: the map is black with pins, exactly as when tiles can't load. */
export const test = base.extend<{ noTiles: void }>({
  noTiles: [
    async ({ context }, use) => {
      await context.route(/tiles\.openfreemap\.org/, (route) => route.abort());
      await use();
    },
    { auto: true },
  ],
});

export { expect } from "@playwright/test";
