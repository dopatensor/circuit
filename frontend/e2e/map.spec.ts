import { expect, resetDemo, test } from "./fixtures";
import { goToTab, mapSettled, signInAs } from "./helpers";

test.beforeEach(() => resetDemo());

test("students see nearby startups as pins and can say they're interested (F2)", async ({ page }) => {
  await signInAs(page, "Ravi");
  await goToTab(page, "Map");
  await expect(page).toHaveURL(/\/map$/);
  await expect(page.getByText(/within 10 km/)).toBeVisible();
  await mapSettled(page);
  const pin = page.getByRole("button", { name: "LedgerLoop, hiring" });
  await expect(pin).toBeVisible();
  await pin.dispatchEvent("click"); // pins can overlap; tap exactly this one

  const sheet = page.getByRole("dialog", { name: "LedgerLoop" });
  await expect(sheet).toBeVisible();
  await expect(sheet).toContainText("match to your skills");
  await expect(sheet.getByRole("link", { name: /Backend Engineering Intern/ })).toBeVisible();
  await sheet.getByRole("button", { name: "I'm interested" }).click();
  await expect(sheet.getByText("You're interested")).toBeVisible();

  // It sticks: the startup page knows too.
  await sheet.getByRole("link", { name: "View startup" }).click();
  await expect(page.getByRole("heading", { name: "LedgerLoop" })).toBeVisible();
  await expect(page.getByText("You're interested")).toBeVisible();
});

test("the filter sheet narrows the map to hiring startups", async ({ page }) => {
  await signInAs(page, "Ravi");
  await goToTab(page, "Map");
  await expect(page.getByRole("button", { name: /, hiring$/ }).first()).toBeVisible();
  await page.getByRole("button", { name: "Filters" }).click();
  const sheet = page.getByRole("dialog", { name: "Filters" });
  await sheet.getByLabel("Hiring now only").check();
  await sheet.getByRole("button", { name: "Show startups" }).click();
  await expect(page.getByRole("button", { name: "Filters · 1" })).toBeVisible();
  await expect(page.getByRole("button", { name: /, not hiring$/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /, hiring$/ }).first()).toBeVisible();
});

test("partner admins see the whole city without a skills score", async ({ page }) => {
  await signInAs(page, "Nandini");
  await goToTab(page, "Map");
  await mapSettled(page);
  const pin = page.getByRole("button", { name: /^TerraGrid Energy, / });
  await pin.dispatchEvent("click"); // the whole city on a phone: pins overlap
  const sheet = page.getByRole("dialog", { name: "TerraGrid Energy" });
  await expect(sheet).toBeVisible();
  await expect(sheet).not.toContainText("match to your skills");
  await expect(sheet.getByRole("button", { name: "I'm interested" })).toHaveCount(0);
  await expect(sheet.getByRole("link", { name: "View startup" })).toBeVisible();
});
