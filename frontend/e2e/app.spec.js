import { test, expect } from '@playwright/test';

test('has title and dashboard renders', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/PharmaGPT/i);

  // Check for Scan Invoice heading or similar
  await expect(page.locator('h1')).toContainText(/Scan Invoice/i);
});

test('navigation between tabs works', async ({ page }) => {
  await page.goto('/');

  // Click on Items tab
  await page.click('text=Items');
  await expect(page).toHaveURL(/.*items/);

  // Click on Inventory tab
  await page.click('text=Inventory');
  await expect(page).toHaveURL(/.*inventory/);
});
