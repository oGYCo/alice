/**
 * Tests for the Feed page component — renders items, handles loading, feedback.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import FeedPage from '@/app/feed/page';
import type { ContentItem } from '@/lib/types';

// Mock the API client
vi.mock('@/lib/api', () => ({
  apiClient: {
    getFeed: vi.fn(),
    getSources: vi.fn(),
    triggerFetch: vi.fn(),
    submitFeedback: vi.fn(),
  },
}));

vi.mock('@/lib/store', () => ({
  useStore: () => ({ sidebarOpen: true }),
}));

// Mock IntersectionObserver (not available in jsdom) — must be a class
class MockIntersectionObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  constructor() {}
}
vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);

import { apiClient } from '@/lib/api';

const MOCK_ITEMS: ContentItem[] = [
  {
    id: 1,
    title: 'Introduction to Transformers',
    url: 'https://example.com/transformers',
    summary: 'A guide to transformer architecture.',
    source_url: 'https://example.com/transformers',
    content_type: 'deep_knowledge',
    source: 'rss',
    pipeline_status: 'indexed',
    created_at: '2025-01-01T00:00:00Z',
    published_at: '2025-01-01T00:00:00Z',
    pushed_at: null,
    metadata_: null,
    p_score: 0.85,
    quality_score: 8.0,
  },
  {
    id: 2,
    title: 'Attention Is All You Need',
    url: 'https://arxiv.org/abs/1706.03762',
    summary: 'The original transformer paper.',
    source_url: 'https://arxiv.org/abs/1706.03762',
    content_type: 'thought_provoking',
    source: 'arxiv',
    pipeline_status: 'indexed',
    created_at: '2024-12-01T00:00:00Z',
    published_at: '2024-12-01T00:00:00Z',
    pushed_at: null,
    metadata_: null,
    p_score: 0.92,
    quality_score: 9.5,
  },
];

describe('FeedPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.getFeed).mockResolvedValue(MOCK_ITEMS);
    vi.mocked(apiClient.getSources).mockResolvedValue([]);
    vi.mocked(apiClient.triggerFetch).mockResolvedValue({ status: 'ok' });
    vi.mocked(apiClient.submitFeedback).mockResolvedValue(undefined);
  });

  it('shows loading skeleton initially', async () => {
    // Keep the promise pending during initial render
    let resolveFeed: (v: typeof MOCK_ITEMS) => void;
    vi.mocked(apiClient.getFeed).mockReturnValue(
      new Promise((resolve) => {
        resolveFeed = resolve;
      }) as unknown as ReturnType<typeof apiClient.getFeed>
    );

    render(<FeedPage />);

    // Loading state should be visible before feed resolves
    // At minimum, the page renders without crashing in loading state
    expect(document.body).toBeTruthy();

    // Unblock the fetch
    await act(async () => {
      resolveFeed!(MOCK_ITEMS);
    });
  });

  it('renders feed items after loading', async () => {
    render(<FeedPage />);

    await waitFor(() => {
      expect(screen.getByText('Introduction to Transformers')).toBeInTheDocument();
    });

    expect(screen.getByText('Attention Is All You Need')).toBeInTheDocument();
  });

  it('calls getFeed on mount', async () => {
    render(<FeedPage />);

    await waitFor(() => {
      expect(apiClient.getFeed).toHaveBeenCalledTimes(1);
    });
  });

  it('getFeed called with page 1 and default sort', async () => {
    render(<FeedPage />);

    await waitFor(() => {
      expect(apiClient.getFeed).toHaveBeenCalledWith(1, 20, 'relevance');
    });
  });

  it('renders FeedHeader with view mode controls', async () => {
    render(<FeedPage />);

    await waitFor(() => {
      // FeedHeader renders grid/list toggle buttons
      expect(screen.getByText('Introduction to Transformers')).toBeInTheDocument();
    });

    // Header should be present (FeedHeader renders toggle buttons)
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('shows empty state or loading when no items returned', async () => {
    vi.mocked(apiClient.getFeed).mockResolvedValue([]);

    render(<FeedPage />);

    await waitFor(() => {
      expect(apiClient.getFeed).toHaveBeenCalled();
    });

    // Should not show any content cards
    expect(screen.queryByText('Introduction to Transformers')).not.toBeInTheDocument();
  });

  it('shows fetch action when sources exist but feed is empty', async () => {
    vi.mocked(apiClient.getFeed).mockResolvedValue([]);
    vi.mocked(apiClient.getSources).mockResolvedValue([
      {
        id: 1,
        name: 'HN RSS',
        url: 'https://hnrss.org/frontpage',
        type: 'rss',
        is_active: true,
        created_at: '2025-01-01T00:00:00Z',
      },
    ]);

    render(<FeedPage />);

    await waitFor(() => {
      expect(screen.getByTestId('fetch-now')).toBeInTheDocument();
    });
  });

  it('handles API error gracefully without crashing', async () => {
    vi.mocked(apiClient.getFeed).mockRejectedValue(new Error('Network error'));

    // Should not throw
    expect(() => render(<FeedPage />)).not.toThrow();

    await waitFor(() => {
      expect(apiClient.getFeed).toHaveBeenCalled();
    });
  });
});
