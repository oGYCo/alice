'use client';

import { Home, Search, Settings, PlusCircle, ChevronLeft } from 'lucide-react';
import Link from 'next/link';
import { useSidebarStore } from '@/lib/store';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: 'Feed', icon: Home },
  { href: '/search', label: 'Search', icon: Search },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
  const { isOpen, toggleSidebar } = useSidebarStore();

  return (
    <aside
      data-testid="sidebar"
      className={cn(
        'flex flex-col h-full bg-card border-r border-border transition-all duration-200',
        isOpen ? 'w-64' : 'w-14'
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
        {navItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm hover:bg-accent hover:text-accent-foreground transition-colors"
          >
            <Icon className="h-4 w-4 shrink-0" />
            {isOpen && <span>{label}</span>}
          </Link>
        ))}
      </nav>

      {/* Sources section */}
      {isOpen && (
        <div className="p-2 border-t border-border">
          <div className="flex items-center justify-between px-3 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
            <span>Sources</span>
            <button className="hover:text-foreground transition-colors" aria-label="Add source">
              <PlusCircle className="h-3.5 w-3.5" />
            </button>
          </div>
          <p className="px-3 py-2 text-xs text-muted-foreground">No sources yet</p>
        </div>
      )}
    </aside>
  );
}
