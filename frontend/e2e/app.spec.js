import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Mock Auth Profile
  await page.route('**/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        email: 'test@example.com',
        name: 'Test User',
        picture: 'https://via.placeholder.com/150'
      }),
    });
  });

  // Mock Drafts
  await page.route('**/invoices/drafts', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  // Inject Mock Token to bypass login
  await page.addInitScript(() => {
    window.localStorage.setItem('auth_token', 'mock-p-token');
  });
});

test('has title and dashboard renders', async ({ page }) => {
  await page.goto('/');

  // Expect title to be PharmaGPT
  await expect(page).toHaveTitle(/PharmaGPT/i);

  // Check for PharmaCouncil logo text in Sidebar
  await expect(page.locator('span:has-text("PharmaCouncil")')).toBeVisible();

  // Check for "Scan Invoice" tab being present
  await expect(page.getByText('Scan Invoice')).toBeVisible();

  // Check for main dashboard header (added for accessibility)
  await expect(page.locator('h1')).toContainText(/Dashboard/i);
});

test('navigation between tabs works', async ({ page }) => {
  await page.goto('/');

  // Wait for sidebar to be visible (confirms we are past login)
  await expect(page.getByText('Items')).toBeVisible();

  // Click on Items tab
  await page.click('text=Items');
  // URL doesn't necessarily change with React state tabs unless using a router,
  // but let's check if the content changes or if the URL was expected to change.
  // In App.jsx, it's just state-based: {activeTab === 'items' && <ItemMaster />}
  // The original test expected URL change: await expect(page).toHaveURL(/.*items/);
  // If the app doesn't use React Router, we should check for content instead.
  await expect(page.getByText(/Manage your inventory items/i).or(page.locator('h2:has-text("Items")'))).toBeVisible();

  // Click on Inventory tab
  await page.click('text=Inventory');
  await expect(page.getByText(/Inventory View/i).or(page.locator('h2:has-text("Inventory")'))).toBeVisible();
});
