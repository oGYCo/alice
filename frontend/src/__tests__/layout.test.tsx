import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '../components/layout/sidebar';

// Mock Next.js Link and navigation
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock('@/lib/store', () => ({
  useSidebarStore: () => ({
    isOpen: true,
    toggleSidebar: vi.fn(),
  }),
}));

describe('Sidebar', () => {
  it('renders with data-testid="sidebar"', () => {
    render(<Sidebar />);
    expect(screen.getByTestId('sidebar')).toBeDefined();
  });

  it('renders Alice title when open', () => {
    render(<Sidebar />);
    expect(screen.getByText('Alice')).toBeDefined();
  });

  it('renders navigation links', () => {
    render(<Sidebar />);
    expect(screen.getByText('Feed')).toBeDefined();
    expect(screen.getByText('Search')).toBeDefined();
    expect(screen.getByText('Settings')).toBeDefined();
  });

  it('renders Sources section when open', () => {
    render(<Sidebar />);
    expect(screen.getByText('Sources')).toBeDefined();
  });
});
