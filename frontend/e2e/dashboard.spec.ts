import { expect, resetDemo, test } from "./fixtures";
import { goToTab, signInAs } from "./helpers";

// Phase 11: the partner dashboard (F8), demo story 5.
test.beforeEach(() => resetDemo());

test("story 5: Nandini sees the regulatory gap ranked, on the map, and the intro split", async ({
  page,
}) => {
  // MapLibre's worker must load (it draws the heat layer and the street tiles).
  const workerErrors: string[] = [];
  page.on("console", (m) => m.type() === "error" && /worker/i.test(m.text()) && workerErrors.push(m.text()));
  await signInAs(page, "Nandini");
  await goToTab(page, "Dashboard");

  // Three big numbers.
  const stats = page.getByTestId("dashboard-stats");
  await expect(stats).toContainText("Members");
  await expect(stats).toContainText("Startups hiring");
  await expect(stats).toContainText("Intros made");

  // The biggest gap, in words and as the first row of the chart's table.
  await expect(page.getByText("Regulatory affairs: 35 needs, 2 offers.")).toBeVisible();
  await page.getByText("Show as a table").click();
  const firstRow = page.getByRole("table").getByRole("row").nth(1);
  await expect(firstRow).toHaveText(/Regulatory affairs\s*35\s*2\s*33/);

  // The gap map starts on the biggest gap and follows the capability picker.
  const areas = page.getByTestId("gap-areas");
  await expect(areas).toContainText("Regulatory affairs: 17 areas");
  // The map loads when it's about to scroll into view.
  await page.getByRole("img", { name: /^Map of where/ }).scrollIntoViewIfNeeded();
  await expect(page.locator("[data-heat-settled]")).toBeVisible();
  await page.getByLabel("Capability").selectOption("clinical_trials");
  await expect(areas).toContainText("Clinical trials:");
  await expect(page.locator("[data-heat-settled]")).toBeVisible();

  // Bridge intros are accepted more often than local ones.
  const split = page.getByTestId("intro-split");
  await expect(split.getByRole("listitem").filter({ hasText: "Local matches" })).toContainText("52%");
  await expect(split.getByRole("listitem").filter({ hasText: "Bridge matches" })).toContainText("80%");
  await expect(split).toContainText("20 of 25 accepted");
  expect(workerErrors).toEqual([]);
});

test("a dashboard section that fails says so and can try again", async ({ page }) => {
  let fail = true;
  await page.route("**/api/dashboard/gaps?*", (route) =>
    fail ? route.fulfill({ status: 500, json: { detail: "boom" } }) : route.fallback(),
  );
  await signInAs(page, "Nandini");
  await goToTab(page, "Dashboard");
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("Something went wrong on our side");
  // The other sections still work.
  await expect(page.getByTestId("intro-split")).toContainText("80%");
  fail = false;
  await alert.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText("Regulatory affairs: 35 needs, 2 offers.")).toBeVisible();
});
