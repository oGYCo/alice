import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const AUTH_COOKIE = 'alice-api-key';
const LOGIN_PATH = '/login';
const API_PATH_PREFIX = '/api/';
const HEALTH_PATH = '/health';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get(AUTH_COOKIE)?.value;

  // Auth for API endpoints is handled by backend X-API-Key validation.
  // Never redirect API/health requests to /login.
  if (pathname.startsWith(API_PATH_PREFIX) || pathname === HEALTH_PATH) {
    return NextResponse.next();
  }

  // Unauthenticated user visiting protected route → send to login
  // Note: we do NOT redirect authenticated users away from /login here.
  // The login page's useEffect silently re-validates the stored key and
  // redirects if still valid — this avoids flashing /feed when the cookie
  // is stale/invalid.
  if (!token && pathname !== LOGIN_PATH) {
    const loginUrl = new URL(LOGIN_PATH, request.url);
    loginUrl.searchParams.set('from', pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Match everything except static assets, images, and API routes.
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)'],
};
