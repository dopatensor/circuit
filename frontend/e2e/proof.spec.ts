import type { Page } from "@playwright/test";
import { expect, resetDemo, test } from "./fixtures";
import { goToTab, signInAs } from "./helpers";

// R2: proof of work. Ravi's GitHub import is saved in the seed (no GitHub calls); Sneha
// is a design student who shows work without code.

test.beforeEach(() => resetDemo());

async function openProof(page: Page) {
  await goToTab(page, "Me");
  await page.getByRole("link", { name: "Manage" }).click();
  await expect(page.getByRole("heading", { name: "Proof of work", level: 1 })).toBeVisible();
}

test("Ravi features and hides repos; his profile shows only what he chose", async ({ page }) => {
  await signInAs(page, "Ravi");
  await openProof(page);
  const github = page.getByRole("region", { name: "GitHub" });
  await expect(github.getByRole("link", { name: "ravi-kumar" })).toBeVisible();
  const verified = github.getByRole("list", { name: "Verified by GitHub" });
  await expect(verified).toContainText("Backend development");
  await expect(verified).toContainText("Data engineering");
  await expect(github).toContainText("2 merged pull requests to other projects");

  // Feature the timetable bot.
  const feature = page.getByRole("button", { name: "Feature college-timetable-bot" });
  await feature.click();
  await expect(page.getByRole("button", { name: "Unfeature college-timetable-bot" })).toHaveAttribute("aria-pressed", "true");

  // Hide the ETL repo, undo, then hide it for real.
  await page.getByRole("button", { name: "Hide shop-ledger-etl" }).click();
  await page.getByRole("status").filter({ hasText: "shop-ledger-etl is hidden." }).getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("button", { name: "Hide shop-ledger-etl" })).toBeVisible();
  await page.getByRole("button", { name: "Hide shop-ledger-etl" }).click();
  await expect(page.getByRole("button", { name: "Show shop-ledger-etl" })).toBeVisible();
  // Hidden repos don't verify skills: Airflow and pandas only came from that repo.
  await expect(verified).not.toContainText("Data engineering");

  // The public profile: featured repos only, nothing hidden.
  await goToTab(page, "Me");
  await page.getByRole("link", { name: "See your profile as others see it" }).click();
  const featured = page.getByRole("list", { name: "Featured repos" });
  await expect(featured).toContainText("gst-invoice-parser");
  await expect(featured).toContainText("college-timetable-bot");
  await expect(featured).not.toContainText("shop-ledger-etl");
  await expect(featured).not.toContainText("dotfiles");
  await expect(page.getByRole("list", { name: "Skills" })).toContainText("Backend development");
  // No horizontal scrolling at either width.
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("disconnecting GitHub deletes the imported data", async ({ page }) => {
  await signInAs(page, "Ravi");
  await openProof(page);
  await page.getByRole("button", { name: "Disconnect GitHub" }).click();
  const confirm = page.getByRole("dialog", { name: "Disconnect GitHub?" });
  await confirm.getByRole("button", { name: "Disconnect and delete" }).click();
  await expect(confirm).toBeHidden();
  await expect(page.getByRole("status").filter({ hasText: "GitHub disconnected" })).toBeVisible();
  const github = page.getByRole("region", { name: "GitHub" });
  await expect(github.getByRole("heading", { name: "Connect GitHub" })).toBeVisible();
  // This test server has no GitHub OAuth app, and says so instead of a broken button.
  await expect(github).toContainText("isn't set up on this server");
  await expect(page.getByRole("list", { name: "Your repos" })).toHaveCount(0);

  await goToTab(page, "Me");
  await page.getByRole("link", { name: "See your profile as others see it" }).click();
  await expect(page.getByText("ravi-kumar")).toHaveCount(0);
  await expect(page.getByText("Show something you've built")).toBeVisible();
});

test("connecting GitHub: off to GitHub and back, then the import shows", async ({ page }) => {
  // There is no GitHub here: the API's start/finish answers are stubbed in the browser,
  // the way GitHub would drive them. The backend's OAuth checks have their own tests.
  let connected = false;
  let finishBody: unknown = null;
  const github = {
    login: "sneha-designs", profile_url: "https://github.example/sneha-designs", homepage_url: null,
    verified_capabilities: [{ capability_id: "frontend_development", evidence: ["TypeScript", "React"], repo_count: 2 }],
    featured_repos: [], original_repos: 2, external_prs_total: 0, external_prs: [], active_weeks_90d: 3,
    last_active_at: null, fetched_at: new Date().toISOString(), status: "ok", status_message: null, source: "oauth",
    connected_at: new Date().toISOString(), next_fetch_at: null, repos: [],
  };
  await page.route("**/api/proof/me", async (route) => {
    const real = await (await route.fetch()).json();
    await route.fulfill({ json: { ...real, github_available: true, github: connected ? github : null } });
  });
  await page.route("**/api/proof/github/start", (route) =>
    route.fulfill({ json: { authorize_url: "/me/github/callback?code=one-time&state=signed-state" } }),
  );
  await page.route("**/api/proof/github/finish", async (route) => {
    finishBody = route.request().postDataJSON();
    connected = true;
    await route.fulfill({ json: github });
  });

  await signInAs(page, "Sneha");
  await openProof(page);
  await page.getByRole("button", { name: "Connect GitHub" }).click();
  await expect(page).toHaveURL(/\/me\/proof$/);
  expect(finishBody).toEqual({ code: "one-time", state: "signed-state" });
  await expect(page.getByRole("status").filter({ hasText: "GitHub connected" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Verified by GitHub" })).toContainText("Frontend development");

  // Saying no on GitHub's page brings you back with a plain sentence.
  await page.goto("/me/github/callback?error=access_denied");
  await expect(page.getByText("You didn't give access on GitHub")).toBeVisible();
});

test("a design student shows work without code", async ({ page }) => {
  await signInAs(page, "Sneha");
  await openProof(page);
  const work = page.getByRole("list", { name: "Other work" });
  await expect(work).toContainText("Kirana billing app: a faster checkout");
  await expect(work).toContainText("Behance");
  await expect(work).toContainText("Case study");
  await expect(work).toContainText("Added by you");

  await page.getByRole("button", { name: "Add work" }).click();
  const sheet = page.getByRole("dialog", { name: "Add work" });
  const save = sheet.getByRole("button", { name: "Save" });
  await sheet.getByLabel("Title").fill("Icon set for a farmers' app");
  await expect(save).toBeDisabled(); // no link: needs a 40-character write-up
  await sheet.getByLabel(/^Link/).fill("dribbble.com/shots/123-farm-icons");
  await sheet.getByLabel(/^What you did/).fill("Thirty icons tested with farmers who read little English.");
  await sheet.getByRole("button", { name: /Show all/ }).click();
  await sheet.getByRole("button", { name: "UI/UX design" }).click();
  await save.click();
  await expect(sheet).toBeHidden();
  const added = work.getByRole("listitem").filter({ hasText: "Icon set for a farmers' app" });
  await expect(added).toContainText("Dribbble");
  await expect(added).toContainText("UI/UX design");

  await added.getByRole("button", { name: /^Remove/ }).click();
  await expect(work.getByText("Icon set for a farmers' app")).toHaveCount(0);
});

test("privacy: a student can hide their college from their profile", async ({ page }) => {
  await signInAs(page, "Sneha");
  await goToTab(page, "Me");
  const toggle = page.getByRole("checkbox", { name: "Show my college on my profile" });
  await expect(toggle).toBeChecked();
  await toggle.uncheck();
  await expect(toggle).not.toBeChecked();
  await page.getByRole("link", { name: "See your profile as others see it" }).click();
  await expect(page.getByRole("heading", { name: "Sneha Pillai" })).toBeVisible();
  await expect(page.getByText("Kalyan Nagar Government Polytechnic")).toHaveCount(0);
});

test("Home: a student without proof of work is pointed at it", async ({ page }) => {
  await signInAs(page, "Sneha");
  await page.route("**/api/members/me", async (route) => {
    const me = await (await route.fetch()).json();
    await route.fulfill({ json: { ...me, proof: { github: null, items: [] } } });
  });
  await page.goto("/home");
  const step = page.getByRole("region", { name: "Your next step" });
  await expect(step.getByRole("heading", { name: "Show something you've built" })).toBeVisible();
  await step.getByRole("link", { name: "Add proof of work" }).click();
  await expect(page.getByRole("heading", { name: "Proof of work", level: 1 })).toBeVisible();
});
