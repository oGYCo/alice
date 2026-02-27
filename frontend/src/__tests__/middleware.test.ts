import type { NextRequest } from 'next/server';
import { describe, expect, it } from 'vitest';
import { middleware } from '../middleware';

function buildRequest(pathname: string, token?: string): NextRequest {
  return {
    nextUrl: { pathname },
    cookies: {
      get: (name: string) =>
        name === 'alice-api-key' && token ? { name, value: token } : undefined,
    },
    url: `http://localhost:3000${pathname}`,
  } as unknown as NextRequest;
}

describe('middleware auth routing', () => {
  it('does not redirect unauthenticated API requests', () => {
    const res = middleware(buildRequest('/api/v1/content'));
    expect(res.headers.get('location')).toBeNull();
  });

  it('does not redirect unauthenticated health requests', () => {
    const res = middleware(buildRequest('/health'));
    expect(res.headers.get('location')).toBeNull();
  });

  it('redirects unauthenticated protected page requests to login', () => {
    const res = middleware(buildRequest('/feed'));
    expect(res.headers.get('location')).toBe('http://localhost:3000/login?from=%2Ffeed');
  });

  it('allows authenticated protected page requests', () => {
    const res = middleware(buildRequest('/feed', 'valid-key'));
    expect(res.headers.get('location')).toBeNull();
  });
});
