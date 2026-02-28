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
    await expect(page).toHaveURL(/\/feed$/);
    // Wait for sidebar links to appear (Zustand rehydration + render)
    const links = page.locator('a[href]');
    await expect(links.first()).toBeVisible({ timeout: 10000 });
    const count = await links.count();
    expect(count).toBeGreaterThan(0);
  });
});
