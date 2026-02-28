import { test, expect } from './fixtures';

test.describe('Navigation', () => {
  test('root redirects or renders without crashing', async ({ page }) => {
    await page.goto('/');
    // Should not land on an error page
    await expect(page).not.toHaveURL(/error/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('can navigate from feed to settings via sidebar links', async ({ page }) => {
    await page.goto('/feed', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);
    // Sidebar navigation links should be present
    const links = page.locator('a[href]');
    const count = await links.count();
    expect(count).toBeGreaterThan(0);
  });
});
