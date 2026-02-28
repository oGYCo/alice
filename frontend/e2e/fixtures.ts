import { test as base } from '@playwright/test';

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
    // Cookie for the server-side middleware
    await context.addCookies([
      {
        name: 'alice-api-key',
        value: 'test-api-key',
        url: 'http://localhost:3000',
      },
    ]);

    // Seed localStorage before any application script executes.
    // This avoids timing races where AuthGuard reads the default
    // unauthenticated state and redirects to /login on slower machines.
    await context.addInitScript(() => {
      window.localStorage.setItem(
        'alice-auth',
        JSON.stringify({
          state: { apiKey: 'test-api-key', isAuthenticated: true },
          version: 0,
        }),
      );
    });

    await runWithPage(page);
  },
});

export { expect } from '@playwright/test';
