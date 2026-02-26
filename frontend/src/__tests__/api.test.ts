import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AliceApiClient } from '../lib/api';

describe('AliceApiClient', () => {
  let client: AliceApiClient;

  beforeEach(() => {
    client = new AliceApiClient('http://localhost:8000');
    global.fetch = vi.fn();
  });

  it('calls correct URL for getContent', async () => {
    const mockContent = [{ id: 1, title: 'Test', url: 'https://example.com', source: 'rss', source_url: 'https://feed.com', pipeline_status: 'indexed', created_at: '2025-01-01T00:00:00Z', summary: null, content_type: null, quality_score: null, p_score: null, published_at: null, pushed_at: null, metadata_: null }];
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify(mockContent), { status: 200 }));
    const result = await client.getContent();
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/v1/content?limit=20&offset=0', expect.any(Object));
    expect(result).toEqual(mockContent);
  });

  it('throws on non-ok response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 }));
    await expect(client.getContent()).rejects.toThrow('Not found');
  });

  it('calls correct URL for searchContent', async () => {
    const mockSearch = { hits: [], total: 0, limit: 20, offset: 0, facets: {} };
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify(mockSearch), { status: 200 }));
    const result = await client.searchContent('AI');
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/v1/search?q=AI&limit=20&offset=0', expect.any(Object));
    expect(result).toEqual(mockSearch);
  });

  it('includes API key header when provided', async () => {
    const clientWithKey = new AliceApiClient('http://localhost:8000', 'test-key');
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
    await clientWithKey.getSources();
    const callArgs = vi.mocked(fetch).mock.calls[0];
    expect((callArgs[1] as RequestInit & { headers: Record<string, string> }).headers['X-API-Key']).toBe('test-key');
  });
});
