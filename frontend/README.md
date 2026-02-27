# Alice Frontend

Next.js App Router UI for Alice.

Current implemented pages:

- `/login` API key login
- `/feed` content feed and feedback actions
- `/content/[id]` content detail
- `/search` full-text search
- `/settings` source + push preference management

## Prerequisites

- Node.js 20+
- npm 10+
- Backend API running on `http://localhost:8000` (or custom `API_URL`)

## Install

```bash
npm install
```

## Run

```bash
npm run dev
```

App URL: `http://localhost:3000`

## Authentication

- Frontend uses API key auth against backend (`X-API-Key` header).
- Login page verifies key by calling `/api/v1/content?limit=1`.
- On success, key is stored in Zustand state and synced to cookie `alice-api-key`.

If backend default key is unchanged, login key is:

```text
alicesecret
```

## API Routing

`next.config.ts` rewrites the following paths to backend origin:

- `/api/v1/:path*` -> `${API_URL or NEXT_PUBLIC_API_URL}/api/v1/:path*`
- `/health` -> `${API_URL or NEXT_PUBLIC_API_URL}/health`

Default backend origin is `http://localhost:8000`.

## Scripts

- `npm run dev` - start dev server
- `npm run build` - production build
- `npm run start` - run production server
- `npm run lint` - run ESLint
- `npm run typecheck` - run TypeScript checks
- `npm run test` - run Vitest test suite once
- `npm run test:watch` - run Vitest in watch mode
- `npm run test:e2e` - run Playwright end-to-end tests

## Testing Notes

- Unit/component tests are under `src/**/__tests__/`.
- Playwright specs are under `e2e/`.
- For meaningful end-to-end verification, start backend + infra first so pages can hit real API responses.
