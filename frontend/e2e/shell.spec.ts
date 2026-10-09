import { expect, test } from "./fixtures";
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

test("everyone gets the same places; the centre button is the role's main action", async ({ page }, testInfo) => {
  const phone = testInfo.project.name === "phone";
  // Phones: Home · Discover · [action] · Circuits · Inbox (Me is your avatar).
  // Laptops: the same places plus Me in the sidebar, and the action as a button.
  const expected = (action: [string, string]) =>
    phone
      ? ["Home", "Discover", action[0], "Circuits", "Inbox"]
      : ["Home", "Discover", "Circuits", "Inbox", "Me", action[1]];

  await signInAs(page, "Ravi");
  await expect(page).toHaveURL(/\/home$/);
  expect(await tabLabels(page)).toEqual(expected(["Jobs", "Find jobs"]));

  await switchTo(page, "Meera");
  await expect(page).toHaveURL(/\/home$/);
  expect(await tabLabels(page)).toEqual(expected(["Post", "Post a job or need"]));

  await switchTo(page, "Lakshmi");
  expect(await tabLabels(page)).toEqual(expected(["Offer", "Offer help"]));

  await switchTo(page, "Nandini");
  expect(await tabLabels(page)).toEqual(expected(["Gaps", "Ecosystem gaps"]));
  await goToTab(page, "Dashboard");
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("Discover holds the browse screens as tabs, and old links still work", async ({ page }) => {
  await signInAs(page, "Ravi");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Discover" }).click();
  await expect(page).toHaveURL(/\/map$/); // students start on the map
  const tabs = page.getByRole("navigation", { name: "Discover" });
  expect(await tabs.getByRole("link").allInnerTexts()).toEqual(["Map", "Jobs", "Matches", "Startups"]);
  await tabs.getByRole("link", { name: "Startups" }).click();
  await expect(page.getByRole("heading", { name: "Startups" })).toBeVisible();
  await page.getByLabel("Startup name").fill("Ledger");
  await expect(page.getByRole("main").getByRole("link", { name: /LedgerLoop/ })).toBeVisible();

  await page.goto("/intros"); // the old Intros tab lives in Inbox now
  await expect(page).toHaveURL(/\/inbox$/);
  await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible();
});

test("pages a role can't use send you home", async ({ page }) => {
  await signInAs(page, "Nandini");
  await page.goto("/matches"); // partner admins have no matches of their own
  await expect(page).toHaveURL(/\/home$/);
  await page.goto("/nowhere");
  await expect(page).toHaveURL(/\/home$/);
  await switchTo(page, "Ravi");
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/home$/);
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
  await expect(page).toHaveURL(/\/home$/);
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
  for (const item of await nav.locator("a, button").all()) {
    expect((await item.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  if (testInfo.project.name === "phone") {
    // Me is your avatar in the top bar, also a 44px target.
    const me = page.getByRole("link", { name: "Me", exact: true });
    expect((await me.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  // No sideways scrolling at either width.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("matches show a reason and the Bridge badge (story 1)", async ({ page }) => {
  await signInAs(page, "Meera");
  await goToTab(page, "Matches");
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
