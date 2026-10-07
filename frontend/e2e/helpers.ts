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

/** Switch person from the Me tab (demo mode). */
export async function switchTo(page: Page, name: string) {
  await goToTab(page, "Me");
  await page.getByRole("button", { name: "Switch person" }).click();
  const sheet = page.getByRole("dialog", { name: "Switch person" });
  await personButton(sheet, name).click();
  await expect(sheet).toBeHidden();
}

/** The visible tab labels (bottom bar on phones, sidebar on laptops). */
export async function tabLabels(page: Page): Promise<string[]> {
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  return page.getByRole("navigation", { name: "Main" }).getByRole("link").allInnerTexts();
}

export async function goToTab(page: Page, label: string) {
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: label }).click();
}
