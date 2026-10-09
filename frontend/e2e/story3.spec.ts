import { expect, resetDemo, test } from "./fixtures";
import { goToTab, signInAs, switchTo } from "./helpers";

test.beforeEach(() => resetDemo());

test("story 3: Ravi applies on skills, Deepak shortlists him, Ravi sees it", async ({ page }) => {
  // Ravi: the top job in the list is the LedgerLoop internship, a 100% skills match.
  await signInAs(page, "Ravi");
  await goToTab(page, "Jobs");
  const top = page.getByRole("main").getByRole("link").filter({ hasText: /\d+%\s*match/ }).first();
  await expect(top).toContainText("Backend Engineering Intern");
  await expect(top).toContainText("LedgerLoop");
  await expect(top).toContainText("100%");
  await top.click();

  await expect(page.getByRole("heading", { name: "Backend Engineering Intern" })).toBeVisible();
  await expect(page.getByText("match to your skills, not your college")).toBeVisible();
  await expect(page.getByText(/^✓ /).first()).toBeVisible(); // matched skills highlighted
  await page.getByRole("button", { name: "Apply" }).click();
  const sheet = page.getByRole("dialog", { name: /^Apply/ });
  await sheet.getByLabel(/short note/).fill("I built a GST invoice parser in Python.");
  await sheet.getByRole("button", { name: "Send application" }).click();
  await expect(sheet).toBeHidden();
  await expect(page.getByText("You applied")).toBeVisible();

  await goToTab(page, "Jobs");
  await page.getByRole("tab", { name: "My applications" }).click();
  const mine = page.getByRole("main").getByRole("link", { name: /Backend Engineering Intern/ });
  await expect(mine).toContainText("Applied");

  // Deepak (LedgerLoop's founder): Me -> LedgerLoop -> applicants, best match first.
  await switchTo(page, "Deepak");
  await goToTab(page, "Me");
  await page.getByRole("link", { name: /LedgerLoop/ }).click();
  await page.getByRole("link", { name: "See applicants" }).click();
  const ravi = page.getByRole("listitem").filter({ hasText: "Ravi Kumar" });
  await expect(ravi).toContainText("100%");
  await expect(ravi).toContainText("GST invoice parser");
  await expect(ravi).not.toContainText("Shantinagar"); // skills, not college
  // R2: his GitHub proof shows next to his skills.
  await expect(ravi.getByRole("list", { name: "Verified by GitHub" })).toContainText("Backend development");
  await ravi.getByRole("button", { name: "Shortlist" }).click();
  await expect(ravi).toContainText("Shortlisted");
  const applicantsUrl = page.url();

  // Another founder can't see LedgerLoop's applicants.
  await switchTo(page, "Meera");
  await page.goto(applicantsUrl);
  await expect(page.getByRole("alert")).toBeVisible();

  // Ravi sees the new status.
  await switchTo(page, "Ravi");
  await goToTab(page, "Jobs");
  await page.getByRole("tab", { name: "My applications" }).click();
  await expect(
    page.getByRole("main").getByRole("link", { name: /Backend Engineering Intern/ }),
  ).toContainText("Shortlisted");
});

test("a student can't apply twice", async ({ page }) => {
  await signInAs(page, "Ravi");
  await goToTab(page, "Jobs");
  await page.getByRole("main").getByRole("link").filter({ hasText: /\d+%\s*match/ }).first().click();
  await page.getByRole("button", { name: "Apply" }).click();
  await page.getByRole("button", { name: "Send application" }).click();
  await expect(page.getByText("You applied")).toBeVisible();
  await page.reload();
  await expect(page.getByText("You applied")).toBeVisible();
  await expect(page.getByRole("button", { name: "Apply" })).toHaveCount(0);
});
