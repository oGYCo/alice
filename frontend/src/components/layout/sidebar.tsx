'use client';

import { useCallback, useEffect, useState } from 'react';
import { Home, Search, Settings, PlusCircle, ChevronLeft, LogOut, LayoutDashboard } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useSidebarStore, useAuthStore } from '@/lib/store';
import { apiClient } from '@/lib/api';
import type { Source } from '@/lib/types';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: 'Feed', icon: Home },
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/search', label: 'Search', icon: Search },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
  const { isOpen, toggleSidebar } = useSidebarStore();
  const { logout } = useAuthStore();
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push('/login');
  };
  const [sources, setSources] = useState<Source[]>([]);
  const [sourcesLoaded, setSourcesLoaded] = useState(false);

  const loadSources = useCallback(async () => {
    try {
      const data = await apiClient.getSources();
      setSources(data);
    } catch {
      setSources([]);
    } finally {
      setSourcesLoaded(true);
    }
  }, []);

  useEffect(() => {
    loadSources();
  }, [loadSources, pathname]);

  useEffect(() => {
    const onSourcesUpdated = () => {
      void loadSources();
    };
    window.addEventListener('sources-updated', onSourcesUpdated);
    return () => window.removeEventListener('sources-updated', onSourcesUpdated);
  }, [loadSources]);

  return (
    <aside
      data-testid="sidebar"
      className={cn(
        'flex flex-col h-full bg-card border-r border-border shadow-[1px_0_8px_rgba(0,0,0,0.05)] transition-all duration-200',
        isOpen ? 'w-50' : 'w-14'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        {isOpen && (
          <span className="font-semibold text-lg tracking-tight">Alice</span>
        )}
        <button
          onClick={toggleSidebar}
          className="p-1 rounded hover:bg-accent transition-colors"
          aria-label="Toggle sidebar"
        >
          <ChevronLeft className={cn('h-4 w-4 transition-transform', !isOpen && 'rotate-180')} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || (href !== '/' && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-accent text-accent-foreground font-medium'
                  : 'hover:bg-accent hover:text-accent-foreground'
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {isOpen && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Sources section */}
      {isOpen && (
        <div className="p-2 border-t border-border">
          <div className="flex items-center justify-between px-3 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
            <span>Sources</span>
            <Link
              href="/settings"
              className="hover:text-foreground transition-colors"
              aria-label="Add source"
            >
              <PlusCircle className="h-3.5 w-3.5" />
            </Link>
          </div>
          {!sourcesLoaded ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">Loading...</p>
          ) : sources.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">No sources yet</p>
          ) : (
            <div className="mt-1 space-y-1">
              {sources.slice(0, 5).map((source) => (
                <div
                  key={source.id}
                  className="px-3 py-1.5 text-xs rounded text-muted-foreground bg-muted/30 truncate"
                  title={source.name}
                >
                  {source.name}
                </div>
              ))}
              {sources.length > 5 && (
                <p className="px-3 py-1 text-xs text-muted-foreground">
                  +{sources.length - 5} more
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Logout */}
      <div className="p-2 border-t border-border">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
          aria-label="Logout"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {isOpen && <span>退出登录</span>}
        </button>
      </div>
    </aside>
  );
}
