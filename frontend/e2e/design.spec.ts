import { expect, resetDemo, test } from "./fixtures";
import { goToTab, signInAs, switchTo } from "./helpers";

// R1: the design system (/design), the theme choice, Home's next step and the founder's
// centre button.

test("the design page shows every building block, with no sideways scrolling", async ({ page }) => {
  await page.goto("/design");
  await expect(page.getByRole("heading", { name: "Design system" })).toBeVisible();
  for (const block of ["Colour", "Type", "Icons", "Buttons", "Avatars", "Badges", "Chips", "Cards and lists", "Path stepper", "Checklist", "Tabs", "Sheets, modals and toasts", "Loading, empty and error"]) {
    await expect(page.getByRole("region", { name: block })).toBeVisible();
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("sheets and modals open, trap focus, and close with Escape or the Close button", async ({ page }) => {
  await page.goto("/design");
  await page.getByRole("button", { name: "Open bottom sheet" }).click();
  const sheet = page.getByRole("dialog", { name: "Filters" });
  await expect(sheet).toBeVisible();
  await expect(sheet.getByRole("heading", { name: "Filters" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();

  await page.getByRole("button", { name: "Open modal" }).click();
  const modal = page.getByRole("dialog", { name: "Withdraw your application?" });
  await expect(modal).toBeVisible();
  await modal.getByRole("button", { name: "Close" }).click();
  await expect(modal).toBeHidden();
  // Focus can reach the page again once it's closed.
  await page.getByRole("button", { name: "Open modal" }).focus();
  await expect(page.getByRole("button", { name: "Open modal" })).toBeFocused();
});

test("phones: dragging a sheet down closes it; a small drag springs back", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "phone", "drag to dismiss is a phone gesture");
  await page.goto("/design");
  await page.getByRole("button", { name: "Open bottom sheet" }).click();
  const sheet = page.getByRole("dialog", { name: "Filters" });
  const title = sheet.getByRole("heading", { name: "Filters" });
  await expect(title).toBeVisible();
  await page.waitForTimeout(400); // let it finish opening

  const drag = async (dy: number) => {
    const box = (await title.boundingBox())!;
    await page.mouse.move(box.x + 20, box.y + 5);
    await page.mouse.down();
    for (let i = 1; i <= 8; i++) await page.mouse.move(box.x + 20, box.y + 5 + (dy * i) / 8);
    await page.mouse.up();
  };
  await drag(40);
  await page.waitForTimeout(500);
  await expect(sheet).toBeVisible();
  await drag(260);
  await expect(sheet).toBeHidden();
});

test("a toast offers Undo, which reverses the action", async ({ page }) => {
  await page.goto("/design");
  await page.getByRole("button", { name: "Save a job" }).click();
  await expect(page.getByRole("button", { name: "Saved" })).toBeVisible();
  const toast = page.getByRole("status").filter({ hasText: "Saved LedgerLoop's internship" });
  await expect(toast).toBeVisible();
  await toast.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("button", { name: "Save a job" })).toBeVisible();
  await expect(toast).toBeHidden();
});

test("tabs move with the arrow keys; chips say whether they're selected", async ({ page }) => {
  await page.goto("/design");
  const tabs = page.getByRole("tablist", { name: "Example tabs" });
  await tabs.getByRole("tab", { name: "People" }).click();
  await page.keyboard.press("ArrowRight");
  await expect(tabs.getByRole("tab", { name: "Startups" })).toBeFocused();
  await expect(tabs.getByRole("tab", { name: "Startups" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel")).toHaveText("Showing startups.");

  const chip = page.getByRole("region", { name: "Chips" }).getByRole("button", { name: "Marketing" });
  await expect(chip).toHaveAttribute("aria-pressed", "false");
  await chip.click();
  await expect(chip).toHaveAttribute("aria-pressed", "true");
});

test("light and dark: follows the device, and a choice on Me sticks after a reload", async ({ browser }, testInfo) => {
  const context = await browser.newContext({ ...testInfo.project.use, colorScheme: "dark" });
  const page = await context.newPage();
  const bg = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  await signInAs(page, "Ravi");
  expect(await bg()).toBe("rgb(17, 17, 16)"); // the device is dark

  await goToTab(page, "Me");
  await page.getByText("Light", { exact: true }).click();
  expect(await bg()).toBe("rgb(251, 250, 248)");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Ravi Kumar" })).toBeVisible();
  expect(await bg()).toBe("rgb(251, 250, 248)");

  await page.getByText("Same as device", { exact: true }).click();
  expect(await bg()).toBe("rgb(17, 17, 16)");
  await context.close();
});

test("Home: each story's person sees their next step first", async ({ page }) => {
  // Story 3: the student is told to apply to the internship that fits him.
  await signInAs(page, "Ravi");
  const step = page.getByRole("region", { name: "Your next step" });
  await expect(step.getByRole("heading", { name: "Apply to Backend Engineering Intern at LedgerLoop" })).toBeVisible();
  await expect(step.getByRole("list", { name: "Your path to an internship" })).toBeVisible();
  await step.getByRole("link", { name: "See the job" }).click();
  await expect(page.getByRole("heading", { name: "Backend Engineering Intern" })).toBeVisible();

  // Story 1: the biotech founder is pointed at the deep-tech marketer.
  await switchTo(page, "Meera");
  await expect(page.getByRole("region", { name: "Your next step" }).getByRole("heading", { name: "Meet Kavya Menon" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Matches for you" })).toContainText("Bridge match");
});

test.describe("founders post a job from the centre button", () => {
  test.beforeEach(() => resetDemo());

  test("Deepak posts an internship and lands on its page", async ({ page }, testInfo) => {
    await signInAs(page, "Deepak");
    const nav = page.getByRole("navigation", { name: "Main" });
    await nav.getByRole("button", { name: testInfo.project.name === "phone" ? "Post" : "Post a job or need" }).click();
    const sheet = page.getByRole("dialog", { name: "What do you want to post?" });
    await sheet.getByRole("button", { name: /Post a job/ }).click();
    await expect(page.getByRole("heading", { name: "Post a job" })).toBeVisible();

    const post = page.getByRole("button", { name: "Post job" });
    await expect(post).toBeDisabled(); // needs a role name and a skill
    await page.getByLabel("Role").fill("Data Engineering Intern");
    await page.getByLabel("Pay (optional)").fill("₹18,000/month");
    await page.getByLabel("What they'll do").fill("Clean invoice data with us and ship a pipeline in month one.");
    await page.getByRole("button", { name: "Data engineering" }).click();
    await post.click();

    await expect(page.getByRole("heading", { name: "Data Engineering Intern" })).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: "Job posted" })).toBeVisible();
  });

  test("a founder without a claimed startup is told to claim one first", async ({ page }) => {
    await signInAs(page, "Rohan"); // TerraGrid is unclaimed in the seed
    await page.goto("/jobs/new");
    await expect(page.getByText("Claim your startup first")).toBeVisible();
    await expect(page.getByRole("link", { name: "Find your startup" })).toBeVisible();
  });
});
