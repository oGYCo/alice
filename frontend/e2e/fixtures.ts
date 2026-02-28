import { test as base } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';
const REAL_API_KEY = process.env.E2E_API_KEY ?? process.env.ALICE_API_KEY ?? 'alicesecret';

/**
 * Extend the default Playwright test with authentication pre-configured.
 *
 * Sets both:
 *   1. The `alice-api-key` cookie (read by Next.js middleware server-side)
 *   2. The Zustand persisted auth state in localStorage (read by AuthGuard
 *      and ConditionalSidebar on the client)
 *
 * All E2E tests that hit authenticated routes should import `test` and
 * `expect` from this module instead of `@playwright/test`.
 */
export const test = base.extend({
  page: async ({ page, context }, runWithPage) => {
    // Cookie for server-side middleware auth checks.
    await context.addCookies([
      {
        name: 'alice-api-key',
        value: REAL_API_KEY,
        domain: 'localhost',
        path: '/',
        sameSite: 'Lax',
      },
    ]);

    // Seed persisted Zustand auth state on a real same-origin page.
    // This is more deterministic than relying only on addInitScript.
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.evaluate((apiKey) => {
      window.localStorage.setItem(
        'alice-auth',
        JSON.stringify({
          state: { apiKey, isAuthenticated: true },
          version: 0,
        }),
      );
    }, REAL_API_KEY);

    await runWithPage(page);
  },
});

export { expect } from '@playwright/test';
