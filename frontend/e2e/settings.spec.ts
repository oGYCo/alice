import { test, expect } from './fixtures';

test.describe('Settings Page', () => {
  test('loads settings page without error', async ({ page }) => {
    await page.goto('/settings');
    await expect(page).not.toHaveURL(/error/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('settings page renders tabs', async ({ page }) => {
    await page.goto('/settings', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    // SettingsPage has tabbed navigation (Sources, Preferences, Schedule, About)
    const tabList = page.locator('[role="tablist"]');
    await expect(tabList).toBeVisible();
    const tabs = page.locator('[role="tab"]');
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });
});
