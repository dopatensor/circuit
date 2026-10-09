import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { goToTab, signInAs, switchTo } from "./helpers";

async function serviceWorkerReady(page: Page) {
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  // The first load isn't controlled by the worker yet; a reload is.
  await page.reload();
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
}

test("the manifest is linked and complete, and every icon loads", async ({ page, request }) => {
  await page.goto("/welcome");
  const href = await page.locator('link[rel="manifest"]').getAttribute("href");
  expect(href).toBeTruthy();
  const manifest = await (await request.get(href!)).json();
  expect(manifest).toMatchObject({
    name: "Circuit",
    short_name: "Circuit",
    display: "standalone",
    start_url: "/",
  });
  const sizes = manifest.icons.map((i: { sizes: string; purpose?: string }) =>
    `${i.sizes}${i.purpose ? ` ${i.purpose}` : ""}`,
  );
  expect(sizes).toEqual(["192x192", "512x512", "512x512 maskable"]);
  for (const icon of manifest.icons) {
    const r = await request.get(icon.src);
    expect(r.ok() && r.headers()["content-type"]).toBe("image/png");
  }
  const apple = await page.locator('link[rel="apple-touch-icon"]').getAttribute("href");
  expect((await request.get(apple!)).ok()).toBe(true);
});

test("the service worker registers and the app opens offline", async ({ page, context }) => {
  await signInAs(page, "Ravi");
  await serviceWorkerReady(page);
  await context.setOffline(true);
  await page.reload();
  // The shell comes from the cache and you're still you: tabs and your name, offline.
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  await goToTab(page, "Me");
  await expect(page.getByRole("heading", { name: "Ravi Kumar" })).toBeVisible();
  await context.setOffline(false);
});

test("jobs, matches and applications stay readable offline; tokens and other people's data don't stay", async ({
  page,
  context,
}) => {
  await signInAs(page, "Ravi");
  await serviceWorkerReady(page);
  const fetchJobs = () =>
    page.evaluate(async () => {
      const r = await fetch("/api/jobs?limit=2", {
        headers: { Authorization: `Bearer ${localStorage.getItem("circuit.token")}` },
      });
      return { ok: r.ok, body: await r.text(), date: r.headers.get("date") };
    });
  const online = await fetchJobs();
  expect(online.ok).toBe(true);

  // The worker writes to its cache just after answering the page, so wait for it.
  const cachedKeys = () =>
    page.evaluate(async () => {
      const cache = await caches.open("circuit-api");
      const keys = await cache.keys();
      return keys.map((k) => ({ url: k.url, auth: k.headers.get("authorization") }));
    });
  await expect
    .poll(async () => (await cachedKeys()).some((k) => k.url.includes("/api/jobs")))
    .toBe(true);
  const cached = await cachedKeys();
  expect(cached.every((k) => k.auth === null)).toBe(true); // the token is never stored
  const allCached = await page.evaluate(async () => {
    const urls: string[] = [];
    for (const name of await caches.keys()) {
      for (const k of await (await caches.open(name)).keys()) urls.push(k.url);
    }
    return urls;
  });
  expect(allCached.some((u) => u.includes("/api/auth"))).toBe(false);

  // Offline: the API can't be reached, also not by the service worker. (setOffline
  // alone doesn't always cover the worker's own requests, so block them too.)
  await context.route("**/api/**", (route) => route.abort("internetdisconnected"));
  await context.setOffline(true);
  const offline = await fetchJobs();
  expect(offline.ok).toBe(true);
  expect(offline.body).toBe(online.body); // the last-loaded copy
  expect(offline.date).toBe(online.date); // so the app can say "Last updated <time>"
  await context.setOffline(false);
  await context.unroute("**/api/**");

  // Switching person clears the previous person's cached data. (Meera's own matches
  // may be cached again straight away; Ravi's jobs must be gone.)
  await switchTo(page, "Meera");
  await expect(page).toHaveURL(/\/home$/);
  const left = await page.evaluate(async () => {
    if (!(await caches.has("circuit-api"))) return [];
    return (await (await caches.open("circuit-api")).keys()).map((k) => k.url);
  });
  expect(left.some((u) => u.includes("/api/jobs"))).toBe(false);
});

test.describe("add to home screen", () => {
  test("iPhone: shown on the second visit with the manual steps, gone once dismissed", async ({
    browser,
  }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "iPhone prompt is a phone-only check");
    const context = await browser.newContext({
      ...testInfo.project.use,
      userAgent:
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 " +
        "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    });
    const first = await context.newPage();
    await signInAs(first, "Ravi");
    const prompt = (p: Page) => p.getByRole("dialog", { name: "Add Circuit to your home screen" });
    await expect(prompt(first)).toHaveCount(0); // first visit: nothing
    await first.close();

    const second = await context.newPage(); // a new tab is a new visit
    await second.goto("/map");
    await expect(prompt(second)).toContainText("tap Share, then “Add to Home Screen”");
    await prompt(second).getByRole("button", { name: "Not now" }).click();
    await expect(prompt(second)).toHaveCount(0);
    await second.close();

    const third = await context.newPage();
    await third.goto("/map");
    await expect(third.getByRole("navigation", { name: "Main" })).toBeVisible();
    await expect(prompt(third)).toHaveCount(0); // one-time
    await context.close();
  });
});
