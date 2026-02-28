'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/lib/store';
import { Sidebar } from './sidebar';

const NO_SIDEBAR_PATHS = ['/login'];

export function ConditionalSidebar() {
    const pathname = usePathname();
    const [storeReady, setStoreReady] = useState(false);
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

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

    if (NO_SIDEBAR_PATHS.includes(pathname)) return null;
    // Don't render sidebar until persist has rehydrated and user is authenticated
    if (!storeReady || !isAuthenticated) return null;
    return <Sidebar />;
}
