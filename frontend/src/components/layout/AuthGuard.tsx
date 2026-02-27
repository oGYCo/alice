'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store';

const PUBLIC_PATHS = ['/login'];

/**
 * Client-side auth guard.
 *
 * On protected routes, renders nothing until the Zustand store has rehydrated
 * from localStorage and confirmed the user is authenticated. This prevents the
 * flash where the page briefly renders before a 401 kicks the user back to login.
 *
 * On public paths (e.g. /login) it passes children through immediately.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
    const [hydrated, setHydrated] = useState(false);
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const pathname = usePathname();
    const router = useRouter();

    useEffect(() => {
        setHydrated(true);
    }, []);

    // After hydration, redirect unauthenticated users — must be in useEffect,
    // never during render, to avoid "setState during render" React errors.
    useEffect(() => {
        if (!hydrated) return;
        const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '?'));
        if (!isPublic && !isAuthenticated) {
            router.replace(`/login?from=${encodeURIComponent(pathname)}`);
        }
    }, [hydrated, isAuthenticated, pathname, router]);

    const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '?'));

    // Always render public pages without guard
    if (isPublic) return <>{children}</>;

    // Render nothing until hydrated, or if about to redirect
    if (!hydrated || !isAuthenticated) return null;

    return <>{children}</>;
}
