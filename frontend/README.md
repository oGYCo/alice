# Alice Frontend

Next.js App Router UI for Alice (feed browsing, content detail, and settings).

## Prerequisites

- Node.js 20+
- npm 10+

## Install

```bash
npm install
```

## Run

```bash
npm run dev
```

App URL: `http://localhost:3000`

## Scripts

- `npm run dev` — start dev server
- `npm run build` — production build
- `npm run start` — run production server
- `npm run lint` — run ESLint
- `npm run typecheck` — run TypeScript checks
- `npm run test` — run Vitest test suite once
- `npm run test:watch` — run Vitest in watch mode
- `npm run test:e2e` — run Playwright end-to-end tests

## Notes

- API calls are centralized in `src/lib/api.ts`.
- By default, frontend calls same-origin `/api/v1/*` and Next.js rewrites to `http://localhost:8000`.
- To target a different backend origin, set `NEXT_PUBLIC_API_URL` (or `API_URL`) before `npm run dev`.
- Unit/component tests are under `src/**/__tests__/`.
- Playwright specs are under `e2e/`.
