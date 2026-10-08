import { expect, resetDemo, test } from "./fixtures";
import { goToTab, signInAs, switchTo } from "./helpers";
import type { Locator, Page } from "@playwright/test";

// Phase 10: onboarding chips (F1), match actions, warm intros (F5), circuits (F6).
test.beforeEach(() => resetDemo());

const card = (page: Page, name: string) =>
  page.getByRole("main").getByRole("article").filter({ has: page.getByRole("heading", { name }) });

async function askForIntro(page: Page, name: string) {
  await goToTab(page, "Matches");
  await card(page, name).getByRole("button", { name: "Ask for intro" }).click();
  return page.getByRole("dialog", { name: `Intro to ${name}` });
}

/** The intro card (in one section of Intros) with this headline. */
const introCard = (section: Locator, headline: string) =>
  section.getByRole("listitem").filter({ has: section.page().getByRole("heading", { name: headline }) });

test("story 1: Meera's Bridge match with Kavya, and the warm path to her", async ({ page }) => {
  await signInAs(page, "Meera");
  await goToTab(page, "Matches");
  const kavya = card(page, "Kavya Menon");
  await expect(kavya).toContainText("Bridge match");
  await expect(kavya).toContainText("offers marketing, which you need");

  const sheet = await askForIntro(page, "Kavya Menon");
  await expect(sheet.getByTestId("intro-path")).toContainText("Nandini Rao");
  await sheet.getByLabel(/Why do you want to meet/).fill("We need help launching to hospital labs.");
  await sheet.getByRole("button", { name: "Send request" }).click();
  await expect(sheet.getByRole("status")).toContainText("Nandini Rao will see it first");

  // Asking twice isn't offered: the sheet points to the open request instead.
  await sheet.getByRole("button", { name: "Close" }).click();
  const again = await askForIntro(page, "Kavya Menon");
  await expect(again).toContainText("You already asked");
});

test("story 4: Rohan reaches Vikram through Lakshmi; Vikram accepts; Rohan rates it", async ({
  page,
}) => {
  await signInAs(page, "Rohan");
  const sheet = await askForIntro(page, "Vikram Shah");
  await expect(sheet.getByTestId("intro-path")).toContainText("Lakshmi");
  await sheet.getByLabel(/Why do you want to meet/).fill("Seed round for grid batteries, 2 pilots live.");
  await sheet.getByRole("button", { name: "Send request" }).click();
  await expect(sheet.getByRole("status")).toContainText("Lakshmi Narayan will see it first");
  await sheet.getByRole("button", { name: "Close" }).click();

  await switchTo(page, "Lakshmi");
  await goToTab(page, "Intros");
  const toPass = page.getByRole("region", { name: "To pass on" });
  const request = introCard(toPass, "Rohan Mehta wants to meet Vikram Shah");
  await expect(request).toContainText("Seed round for grid batteries");
  await request.getByRole("button", { name: "Pass it on" }).click();
  await expect(request).toContainText("Passed on");

  await switchTo(page, "Vikram");
  await goToTab(page, "Intros");
  const forVikram = introCard(page.getByRole("region", { name: "For you" }), "Rohan Mehta wants to meet you");
  await forVikram.getByRole("button", { name: "Accept" }).click();
  await expect(forVikram).toContainText("Accepted");

  await switchTo(page, "Rohan");
  await goToTab(page, "Intros");
  const mine = introCard(page.getByRole("region", { name: "You asked" }), "You asked to meet Vikram Shah");
  await expect(mine).toContainText("Accepted");
  await mine.getByRole("button", { name: "5 of 5" }).click();
  await expect(mine).toContainText("You rated it 5 of 5.");
  await expect(mine).toContainText("Done");
});

test("intros need role verification: a level-2 founder is told why, politely", async ({ page }) => {
  await signInAs(page, "Asha");
  const sheet = await askForIntro(page, "Priya Sharma");
  await expect(sheet.getByRole("alert")).toContainText("need verification level 3");
  await expect(sheet.getByRole("button", { name: "Send request" })).toHaveCount(0);
});

test("story 2: the admin runs a round; Asha, Priya and Arjun accept the loop", async ({ page }) => {
  await signInAs(page, "Nandini");
  await goToTab(page, "Dashboard");
  await page.getByRole("button", { name: "Run round now" }).click();
  const result = page.getByTestId("round-result");
  await expect(result).toContainText("1 proposed");
  await expect(result).toContainText("Asha Reddy");

  for (const [name, gives] of [
    ["Asha", "You help Arjun Nair with hiring"],
    ["Priya", "You help Asha Reddy with marketing"],
    ["Arjun", "You help Priya Sharma with fundraising"],
  ]) {
    await switchTo(page, name);
    await goToTab(page, "Circuits");
    const loop = page.getByTestId("loop-card").first();
    await expect(loop.getByRole("list", { name: "Who helps whom" }).getByRole("listitem").first()).toContainText(gives);
    await expect(loop).toContainText(/Answer within 7[12] hours/);
    await loop.getByRole("button", { name: "Accept" }).click();
    await expect(loop.getByRole("button", { name: "Accept" })).toHaveCount(0);
  }
  const loop = page.getByTestId("loop-card").first();
  await expect(loop).toContainText("Active");

  // Once active, Arjun rates the help he got from Asha with hiring.
  await expect(loop).toContainText("Rate the help you got from Asha Reddy with hiring");
  await loop.getByRole("button", { name: "4 of 5" }).click();
  await expect(loop).toContainText("Done · 4/5");
});

test("a declined circuit is called off for everyone", async ({ page }) => {
  await signInAs(page, "Nandini");
  await goToTab(page, "Dashboard");
  await page.getByRole("button", { name: "Run round now" }).click();
  await expect(page.getByTestId("round-result")).toContainText("1 proposed");
  await switchTo(page, "Priya");
  await goToTab(page, "Circuits");
  await page.getByTestId("loop-card").getByRole("button", { name: "Decline" }).click();
  await expect(page.getByTestId("loop-card")).toContainText("Called off");
});

test("onboarding (F1): without an AI key, pick chips by hand and save", async ({ page }) => {
  await signInAs(page, "Asha");
  await goToTab(page, "Me");
  await page.getByRole("link", { name: "Edit" }).click();
  await expect(page.getByRole("heading", { name: "What you need and offer" })).toBeVisible();

  // Suggestions fall back to the manual pickers.
  await page.getByLabel("Describe yourself or your startup").fill("We sell handloom sarees online and need marketing help.");
  await page.getByRole("button", { name: "Suggest chips" }).click();
  await expect(page.getByRole("status")).toContainText("pick from the lists below");

  // Her current needs are already chosen; add one more from the full list.
  const needs = page.getByRole("region", { name: "What you need" });
  await expect(needs.getByRole("button", { name: /Marketing/, pressed: true }).first()).toBeVisible();
  await needs.getByRole("button", { name: /^Show all/ }).click();
  const legal = needs.getByRole("button", { name: "Legal & contracts", exact: true });
  await legal.click();
  await expect(needs.getByRole("button", { name: /Legal & contracts/, pressed: true })).toBeVisible();

  await page.getByRole("button", { name: "Save and see matches" }).click();
  await expect(page.getByRole("heading", { name: "Matches" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Saved");

  // It stuck.
  await page.getByRole("link", { name: "Edit what you need and offer" }).click();
  await expect(
    page.getByRole("region", { name: "What you need" }).getByRole("button", { name: /Legal & contracts/, pressed: true }),
  ).toBeVisible();
});

test("onboarding (F1): suggested chips are pre-selected and can be changed", async ({ page }) => {
  // No API key in tests, so stand in for the model's answer (same shape as the API's).
  await page.route("**/api/onboarding/suggest", (route) =>
    route.fulfill({
      json: {
        source: "llm",
        fallback_reason: null,
        suggestions: {
          needs: [{ capability_id: "regulatory_affairs", text: "CDSCO approval for a diagnostic kit" }],
          offers: [{ capability_id: "market_research", text: "Hospital lab interviews" }],
          skills: [],
          traits: ["long_sales_cycle"],
        },
      },
    }),
  );
  await signInAs(page, "Meera");
  await goToTab(page, "Me");
  await page.getByRole("link", { name: "Edit" }).click();
  await page.getByLabel("Describe yourself or your startup").fill("We make rapid TB tests for district hospitals.");
  await page.getByRole("button", { name: "Suggest chips" }).click();
  await expect(page.getByRole("status")).toContainText("We picked 3 from what you wrote");

  const needs = page.getByRole("region", { name: "What you need" });
  await expect(needs.getByRole("button", { pressed: true })).toHaveText(["✓ Regulatory affairs"]);
  const offers = page.getByRole("region", { name: "What you offer" });
  await expect(offers.getByRole("button", { pressed: true })).toHaveText(["✓ Market research"]);
  // Tap to change: drop the suggested offer.
  await offers.getByRole("button", { name: "Market research" }).click();
  await expect(offers.getByRole("button", { pressed: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Save and see matches" }).click();
  await expect(page.getByRole("status")).toContainText("Saved");
});
