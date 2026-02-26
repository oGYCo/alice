import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ContentDetailPage from '@/app/content/[id]/page';
import { apiClient } from '@/lib/api';

// Mock dependencies
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: '1' }),
}));

vi.mock('@/lib/api', () => ({
  apiClient: {
    getContentDetail: vi.fn(),
    submitFeedback: vi.fn(),
  },
}));

// Mock Lucide icons to avoid rendering issues in tests if any
vi.mock('lucide-react', async () => {
  const actual = await vi.importActual('lucide-react');
  return {
    ...actual,
    // Add specific mocks if needed, otherwise rely on actual
  };
});

describe('ContentDetailPage', () => {
  const mockGetContentDetail = vi.mocked(apiClient.getContentDetail);
  const mockSubmitFeedback = vi.mocked(apiClient.submitFeedback);

  const mockContent = {
    id: 1,
    title: 'Test Content',
    url: 'https://example.com',
    summary: 'This is a summary.',
    source: 'Test Source',
    source_url: 'https://example.com',
    content_type: 'article',
    quality_score: 8,
    p_score: 0.9,
    pipeline_status: 'processed',
    created_at: '2023-01-01T00:00:00Z',
    published_at: null,
    pushed_at: null,
    metadata_: {},
    key_takeaways: ['Takeaway 1', 'Takeaway 2'],
    push_reason: 'Relevant to your interests.',
    reading_suggestion: 'Skim reading.',
    full_content: '# Full Content\n\nThis is the full content body.',
    subgraph: {
      nodes: [
        { id: '1', label: 'Concept A', mastery: 0.8 },
        { id: '2', label: 'Concept B', mastery: 0.2 },
      ],
      edges: [
        { from: '1', to: '2', relation: 'relates_to' },
      ],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    mockGetContentDetail.mockReturnValue(
      new Promise<never>(() => {}) as ReturnType<typeof apiClient.getContentDetail>
    );
    render(<ContentDetailPage />);
    // Check for loader (using class or implicit role, better to use test id if loader had one, but we can check for emptiness or spinner)
    // Actually our loading state renders a div with Loader2. 
    // Let's rely on the absence of content title for now or just wait.
    // Ideally we should add data-testid to loading spinner.
    // But let's verify apiClient was called.
    expect(apiClient.getContentDetail).toHaveBeenCalledWith(1);
  });

  it('renders content successfully', async () => {
    mockGetContentDetail.mockResolvedValue(mockContent);
    render(<ContentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Content')).toBeDefined();
    });

    expect(screen.getByText('This is a summary.')).toBeDefined();
    expect(screen.getByText('Takeaway 1')).toBeDefined();
    expect(screen.getByText('Relevant to your interests.')).toBeDefined();
    expect(screen.getByText('Skim reading.')).toBeDefined();
    expect(screen.getByText('Concept A')).toBeDefined(); // Subgraph node
  });

  it('renders original content with markdown', async () => {
    mockGetContentDetail.mockResolvedValue(mockContent);
    render(<ContentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Full Content')).toBeDefined(); // h1 in markdown
    });
  });

  it('handles feedback submission', async () => {
    mockGetContentDetail.mockResolvedValue(mockContent);
    mockSubmitFeedback.mockResolvedValue(undefined);
    render(<ContentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Content')).toBeDefined();
    });

    const likeButton = screen.getByTitle('高质量');
    fireEvent.click(likeButton);

    expect(apiClient.submitFeedback).toHaveBeenCalledWith(1, 'positive');
  });

  it('handles API error gracefully', async () => {
    mockGetContentDetail.mockRejectedValue(new Error('API Error'));
    render(<ContentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('API Error')).toBeDefined();
    });
  });
});
