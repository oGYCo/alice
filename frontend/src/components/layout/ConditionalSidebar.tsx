'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/lib/store';
import { Sidebar } from './sidebar';

const NO_SIDEBAR_PATHS = ['/login'];

export function ConditionalSidebar() {
    const pathname = usePathname();
    const [hydrated, setHydrated] = useState(false);
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    useEffect(() => {
        setHydrated(true);
    }, []);

    if (NO_SIDEBAR_PATHS.includes(pathname)) return null;
    // Don't render sidebar until we know the user is authenticated
    if (!hydrated || !isAuthenticated) return null;
    return <Sidebar />;
}
