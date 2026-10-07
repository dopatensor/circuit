import { expect, type Page } from "@playwright/test";

/** Sign in as a demo person from the welcome screen (one tap). */
export async function signInAs(page: Page, name: string) {
  await page.goto("/welcome");
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
}

/** The visible tab labels (bottom bar on phones, sidebar on laptops). */
export async function tabLabels(page: Page): Promise<string[]> {
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  return page.getByRole("navigation", { name: "Main" }).getByRole("link").allInnerTexts();
}

export async function goToTab(page: Page, label: string) {
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: label }).click();
}
