'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store';

const PUBLIC_PATHS = ['/login'];

/**
 * Client-side auth guard.
 *
 * On protected routes, renders nothing until the Zustand persist middleware
 * has finished rehydrating from localStorage and the auth state is known.
 * This prevents the flash where the default state (isAuthenticated: false)
 * triggers a redirect before the persisted authenticated state is restored.
 *
 * On public paths (e.g. /login) it passes children through immediately.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
    const [storeReady, setStoreReady] = useState(false);
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const pathname = usePathname();
    const router = useRouter();

    // Wait for Zustand persist to finish rehydrating from localStorage.
    // Unlike a plain useEffect(() => setHydrated(true)), this hooks into
    // the actual persist rehydration lifecycle so we never act on stale
    // default state.  Must be in useEffect because .persist is undefined
    // during SSR.
    useEffect(() => {
        const persist = useAuthStore.persist;
        if (persist?.hasHydrated?.()) {
            setStoreReady(true);
            return;
        }
        const unsub = persist?.onFinishHydration?.(() => {
            setStoreReady(true);
        });
        return () => { unsub?.(); };
    }, []);

    // After store rehydration, redirect unauthenticated users — must be in
    // useEffect, never during render, to avoid "setState during render" errors.
    useEffect(() => {
        if (!storeReady) return;
        const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '?'));
        if (!isPublic && !isAuthenticated) {
            router.replace(`/login?from=${encodeURIComponent(pathname)}`);
        }
    }, [storeReady, isAuthenticated, pathname, router]);

    const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '?'));

    // Always render public pages without guard
    if (isPublic) return <>{children}</>;

    // Render nothing until persist has rehydrated, or if about to redirect
    if (!storeReady || !isAuthenticated) return null;

    return <>{children}</>;
}
