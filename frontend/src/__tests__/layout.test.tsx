import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '../components/layout/sidebar';

// Mock Next.js Link and navigation
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/feed',
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/lib/store', () => ({
  useSidebarStore: () => ({
    isOpen: true,
    toggleSidebar: vi.fn(),
  }),
  useAuthStore: () => ({
    logout: vi.fn(),
  }),
}));

vi.mock('@/lib/api', () => ({
  apiClient: {
    getSources: vi.fn().mockResolvedValue([]),
  },
}));

describe('Sidebar', () => {
  it('renders with data-testid="sidebar"', async () => {
    render(<Sidebar />);
    expect(await screen.findByTestId('sidebar')).toBeDefined();
  });

  it('renders Alice title when open', async () => {
    render(<Sidebar />);
    expect(await screen.findByText('Alice')).toBeDefined();
  });

  it('renders navigation links', async () => {
    render(<Sidebar />);
    expect(await screen.findByText('Feed')).toBeDefined();
    expect(await screen.findByText('Search')).toBeDefined();
    expect(await screen.findByText('Settings')).toBeDefined();
  });

  it('renders Sources section when open', async () => {
    render(<Sidebar />);
    expect(await screen.findByText('Sources')).toBeDefined();
  });
});
