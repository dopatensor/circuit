import { expect, resetDemo, test } from "./fixtures";
import { goToTab, signInAs } from "./helpers";

test.beforeEach(() => resetDemo());

test("a founder finds and claims their startup with a work email (F3)", async ({ page }) => {
  await signInAs(page, "Rohan");
  await goToTab(page, "Me");
  await page.getByRole("link", { name: "Find and claim your startup" }).click();
  await page.getByLabel("Startup name").fill("TerraGrid");
  await page.getByRole("link", { name: /TerraGrid/ }).click();

  // The interest that motivates claiming is visible before claiming.
  await expect(page.getByText("Not on Circuit yet")).toBeVisible();
  await expect(page.getByText(/1\d students are interested in TerraGrid/)).toBeVisible();
  await page.getByRole("button", { name: "Claim this startup" }).click();

  const sheet = page.getByRole("dialog", { name: "Claim TerraGrid" });
  await sheet.getByLabel(/Your work email/).fill("rohan@gmail.com");
  await sheet.getByRole("button", { name: "Send me a code" }).click();
  await expect(sheet.getByRole("alert")).toContainText("Use an email address at terragrid.example");

  await sheet.getByLabel(/Your work email/).fill("rohan@terragrid.example");
  await sheet.getByRole("button", { name: "Send me a code" }).click();
  await expect(sheet).toContainText("Demo: no email is sent");
  await sheet.getByRole("button", { name: "Use it" }).click();
  await sheet.getByRole("button", { name: "Claim TerraGrid" }).click();

  await expect(sheet).toBeHidden();
  await expect(page.getByText("You manage this page")).toBeVisible();
  await page.getByRole("link", { name: "See applicants" }).click();
  await expect(page.getByText(/No applications yet|Ravi|Applicants/).first()).toBeVisible();

  // It now shows under "Your startups" in Me.
  await goToTab(page, "Me");
  await expect(page.getByRole("link", { name: /TerraGrid/ })).toBeVisible();
});
