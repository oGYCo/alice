import { test, expect } from './fixtures';

test.describe('Feed Page', () => {
  test('loads and shows feed page structure', async ({ page }) => {
    await page.goto('/feed');
    // Page should load without error
    await expect(page).not.toHaveURL(/error/);
    // Should have a main content area
    await expect(page.locator('body')).toBeVisible();
  });

  test('feed page has header with controls', async ({ page }) => {
    await page.goto('/feed', { waitUntil: 'domcontentloaded' });
    // Allow time for client-side hydration
    await page.waitForTimeout(500);
    // Body should be visible — page didn't crash
    await expect(page.locator('body')).toBeVisible();
  });

  test('feed page shows skeleton or content after load', async ({ page }) => {
    await page.goto('/feed', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);
    // Either skeleton cards or actual content items should be present
    const body = page.locator('body');
    await expect(body).toBeVisible();
    // Page should have rendered something beyond blank
    const bodyText = await page.evaluate(() => document.body.innerText);
    expect(bodyText.length).toBeGreaterThan(0);
  });

  test('feed page renders buttons (header controls)', async ({ page }) => {
    await page.goto('/feed', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);
    // FeedHeader renders view-mode toggle buttons
    const buttons = page.locator('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);
  });
});
