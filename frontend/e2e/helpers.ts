import { expect, type Locator, type Page } from "@playwright/test";

/** The button for a demo person (its accessible name starts with their name). */
export function personButton(scope: Page | Locator, name: string) {
  return scope.getByRole("button", { name: new RegExp(`^(Dr\\. )?${name}`) });
}

/** Sign in as a demo person from the welcome screen (one tap). */
export async function signInAs(page: Page, name: string) {
  await page.goto("/welcome");
  await personButton(page, name).click();
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
}

/** Switch person from Me (demo mode). */
export async function switchTo(page: Page, name: string) {
  await goToTab(page, "Me");
  await page.getByRole("button", { name: "Switch person" }).click();
  const sheet = page.getByRole("dialog", { name: "Switch person" });
  await personButton(sheet, name).click();
  await expect(sheet).toBeHidden();
}

/** The visible labels in the main navigation (bottom bar on phones, sidebar on
 *  laptops), links and the centre action button alike. */
export async function tabLabels(page: Page): Promise<string[]> {
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav).toBeVisible();
  return (await nav.locator("a, button").allInnerTexts()).map((t) => t.trim());
}

// Older destinations and where they live now: Discover's tabs, and Inbox for intros.
const DISCOVER_TABS = new Set(["Map", "Jobs", "Matches", "Startups"]);
const RENAMED: Record<string, string> = { Intros: "Inbox", Dashboard: "Gaps" };

/** Go somewhere through the navigation, the way a person would: the main nav, Me
 *  (your avatar on phones), or a Discover tab. */
export async function goToTab(page: Page, label: string) {
  const nav = page.getByRole("navigation", { name: "Main" });
  if (label === "Me") {
    await page.getByRole("link", { name: "Me", exact: true }).click();
    await expect(page).toHaveURL(/\/me$/);
    return;
  }
  await expect(nav).toBeVisible();
  const name = RENAMED[label] ?? label;
  // The student's centre button is "Jobs"; the partner admin's is "Gaps".
  const direct = nav.getByRole("link", { name, exact: true });
  if ((await direct.count()) > 0) return direct.click();
  if (!DISCOVER_TABS.has(label)) throw new Error(`No way to reach "${label}" from the navigation`);
  await nav.getByRole("link", { name: "Discover", exact: true }).click();
  await page.getByRole("navigation", { name: "Discover" }).getByRole("link", { name: label, exact: true }).click();
}

/** Wait until the map has zoomed to its pins and stopped moving. */
export async function mapSettled(page: Page) {
  await expect(page.locator("[data-map-settled]")).toBeVisible();
}
