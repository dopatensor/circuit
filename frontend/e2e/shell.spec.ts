import { expect, test } from "@playwright/test";
import { goToTab, personButton, signInAs, switchTo, tabLabels } from "./helpers";

test("signed out, you land on the welcome screen with the demo people", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/welcome$/);
  await expect(page.getByRole("heading", { name: /Match on what you need/ })).toBeVisible();
  for (const story of ["Bridge match", "Exchange circuit", "Student hired on skills", "Warm intro", "Ecosystem gaps"]) {
    await expect(page.getByRole("region", { name: new RegExp(story) })).toBeVisible();
  }
  for (const name of ["Ravi", "Meera", "Lakshmi", "Nandini", "Deepak"]) {
    await expect(personButton(page, name)).toBeVisible();
  }
});

test("each role gets its own tabs and home tab", async ({ page }) => {
  await signInAs(page, "Ravi");
  await expect(page).toHaveURL(/\/map$/);
  expect(await tabLabels(page)).toEqual(["Map", "Jobs", "Matches", "Me"]);

  await switchTo(page, "Meera");
  await expect(page).toHaveURL(/\/matches$/);
  expect(await tabLabels(page)).toEqual(["Matches", "Circuits", "Intros", "Me"]);

  await switchTo(page, "Nandini");
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(await tabLabels(page)).toEqual(["Dashboard", "Map", "Me"]);
});

test("tabs a role doesn't have send you home", async ({ page }) => {
  await signInAs(page, "Nandini");
  await page.goto("/jobs");
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto("/nowhere");
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("Me shows who you are, your verification and the persona switcher", async ({ page }) => {
  await signInAs(page, "Ravi");
  await goToTab(page, "Me");
  await expect(page.getByRole("heading", { name: "Ravi Kumar" })).toBeVisible();
  await expect(page.getByTestId("verification-badge")).toHaveText("Work verified");
  await expect(page.getByText("You can see your matches.")).toBeVisible();
  await expect(page.getByRole("main").getByText("Applications")).toBeVisible(); // student stats

  await page.getByRole("button", { name: "Switch person" }).click();
  const sheet = page.getByRole("dialog", { name: "Switch person" });
  await expect(sheet.getByRole("button", { name: /^Ravi Kumar.*You$/ })).toBeDisabled();
  await sheet.getByRole("button", { name: "Close" }).click();
  await expect(sheet).toBeHidden();

  await switchTo(page, "Lakshmi");
  await goToTab(page, "Me");
  await expect(page.getByRole("heading", { name: "Dr. Lakshmi Narayan" })).toBeVisible();
  await expect(page.getByTestId("verification-badge")).toHaveText("Role verified");
  await expect(page.getByRole("main").getByText("Circuits", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/welcome$/);
  await page.reload();
  await expect(page).toHaveURL(/\/welcome$/); // stays signed out
});

test("signed in stays signed in after a reload", async ({ page }) => {
  await signInAs(page, "Meera");
  await page.reload();
  await expect(page).toHaveURL(/\/matches$/);
  expect(await tabLabels(page)).toContain("Circuits");
});

test("layout: bottom tabs on phones, sidebar on laptops, 44px tap targets", async ({
  page,
}, testInfo) => {
  await signInAs(page, "Ravi");
  const nav = page.getByRole("navigation", { name: "Main" });
  const box = (await nav.boundingBox())!;
  const viewport = page.viewportSize()!;
  if (testInfo.project.name === "phone") {
    expect(box.y + box.height).toBeCloseTo(viewport.height, 0);
    expect(box.width).toBe(viewport.width);
  } else {
    expect(box.x).toBeLessThan(40);
    expect(box.y).toBeLessThan(120);
  }
  for (const link of await nav.getByRole("link").all()) {
    expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  // No sideways scrolling at either width.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("matches show a reason and the Bridge badge (story 1)", async ({ page }) => {
  await signInAs(page, "Meera");
  const kavya = page.getByRole("article").filter({ hasText: "Kavya Menon" });
  await expect(kavya).toBeVisible();
  await expect(kavya).toContainText("Bridge match");
  await expect(kavya).toContainText("long sales cycle");
});

test("an expired or reset session signs you out cleanly", async ({ page }) => {
  await signInAs(page, "Ravi");
  await page.evaluate(() => localStorage.setItem("circuit.token", "not-a-real-token"));
  await page.reload();
  await expect(page).toHaveURL(/\/welcome$/);
});
