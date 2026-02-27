import type { ContentItem, ContentDetail, SearchResult, SearchHit, HybridSearchResult, Source, PushPreferences, DashboardStats, KGGraph, KGCommunity, KGGapAnalysis } from './types';
import { useAuthStore } from './store';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

export class AliceApiClient {
  private baseUrl: string;

  constructor(baseUrl = BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private getApiKey(): string | null {
    // Always read current key from store — avoids stale singleton state
    try {
      return useAuthStore.getState().apiKey;
    } catch {
      return null;
    }
  }

  private buildUrl(path: string): string {
    if (path.startsWith('http://') || path.startsWith('https://')) {
      return path;
    }
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    if (!this.baseUrl) {
      return normalizedPath;
    }
    const normalizedBase = this.baseUrl.endsWith('/') ? this.baseUrl.slice(0, -1) : this.baseUrl;
    return `${normalizedBase}${normalizedPath}`;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(this.getApiKey() ? { 'X-API-Key': this.getApiKey()! } : {}),
      ...(options.headers as Record<string, string> ?? {}),
    };
    const url = this.buildUrl(path);
    let response: Response;
    try {
      response = await fetch(url, { ...options, headers });
    } catch (error) {
      const cause = error instanceof Error ? error.message : 'unknown network error';
      throw Object.assign(new Error(`Failed to fetch ${url} (${cause})`), { status: 0, cause: error });
    }

    if (!response.ok) {
      // On 401, clear auth state. The AuthGuard client component watches
      // isAuthenticated and will redirect to /login without a page flash.
      if (response.status === 401) {
        useAuthStore.getState().logout();
      }
      const error = await response
        .json()
        .catch(() => ({ detail: response.statusText })) as { detail?: string; message?: string };
      throw Object.assign(new Error(error.detail ?? error.message ?? response.statusText), { status: response.status });
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return response.json() as Promise<T>;
  }

  async getContent(limit = 20, offset = 0): Promise<ContentItem[]> {
    return this.request(`/api/v1/content?limit=${limit}&offset=${offset}`);
  }

  async getContentDetail(id: number): Promise<ContentDetail> {
    return this.request(`/api/v1/content/${id}`);
  }

  async searchContent(
    q: string,
    options: { limit?: number; offset?: number; type?: string; min_score?: number } = {},
  ): Promise<SearchResult> {
    const { limit = 20, offset = 0, type, min_score } = options;
    const params = new URLSearchParams({
      q: q,
      limit: String(limit),
      offset: String(offset),
    });
    if (type) params.set('type', type);
    if (min_score !== undefined) params.set('min_score', String(min_score));
    const raw = await this.request<{ hits: (Omit<SearchHit, 'id'> & { id: string | number })[]; total: number; limit: number; offset: number; facets: Record<string, Record<string, number>> }>(
      `/api/v1/search?${params.toString()}`,
    );
    return {
      ...raw,
      // Meilisearch stores id as string; coerce to number for consistent typing
      hits: raw.hits.map(h => ({ ...h, id: Number(h.id) })) as SearchHit[],
    };
  }

  async getSuggestions(q: string, limit = 5): Promise<string[]> {
    if (!q.trim()) return [];
    const params = new URLSearchParams({ q, limit: String(limit) });
    const raw = await this.request<{ suggestions: string[]; query: string }>(
      `/api/v1/search/suggest?${params.toString()}`,
    );
    return raw.suggestions;
  }

  async hybridSearch(
    q: string,
    options: { mode?: string; user_id?: number; limit?: number } = {},
  ): Promise<HybridSearchResult> {
    const { mode = 'hybrid', user_id = 1, limit = 10 } = options;
    const params = new URLSearchParams({
      q,
      mode,
      user_id: String(user_id),
      limit: String(limit),
    });
    return this.request<HybridSearchResult>(
      `/api/v1/search/hybrid?${params.toString()}`,
      { method: 'POST' },
    );
  }

  async getFeed(page = 1, limit = 20, sort = 'relevance'): Promise<ContentItem[]> {
    const safePage = Math.max(1, page);
    const offset = (safePage - 1) * limit;
    return this.request(`/api/v1/content?limit=${limit}&offset=${offset}&sort=${encodeURIComponent(sort)}`);
  }

  async triggerFetch(sourceId?: number): Promise<Record<string, unknown>> {
    return this.request('/api/v1/pipeline/fetch/trigger', {
      method: 'POST',
      body: JSON.stringify(sourceId ? { source_id: sourceId } : {}),
    });
  }

  async submitFeedback(contentId: number, type: string): Promise<void> {
    return this.request('/api/v1/feedback', {
      method: 'POST',
      body: JSON.stringify({ content_id: contentId, feedback_type: type }),
    });
  }

  async getSources(): Promise<Source[]> {
    return this.request('/api/v1/sources');
  }

  async getPushPreferences(userId: number): Promise<PushPreferences> {
    return this.request(`/api/v1/settings/push?user_id=${userId}`);
  }
  async createSource(data: { name: string; url: string; type: string }): Promise<Source> {
    return this.request('/api/v1/sources', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteSource(id: number): Promise<void> {
    return this.request(`/api/v1/sources/${id}`, {
      method: 'DELETE',
    });
  }

  async deleteContent(id: number): Promise<void> {
    return this.request(`/api/v1/content/${id}`, {
      method: 'DELETE',
    });
  }

  async deleteContentBatch(ids: number[]): Promise<{ deleted: number }> {
    return this.request('/api/v1/content', {
      method: 'DELETE',
      body: JSON.stringify({ ids }),
    });
  }

  async updatePushPreferences(userId: number, prefs: Partial<PushPreferences>): Promise<PushPreferences> {
    return this.request(`/api/v1/settings/push?user_id=${userId}`, {
      method: 'PUT',
      body: JSON.stringify(prefs),
    });
  }

  async healthCheck(): Promise<{ status: string }> {
    return this.request('/health');
  }

  async getDashboardStats(userId = 1): Promise<DashboardStats> {
    return this.request(`/api/v1/dashboard/stats?user_id=${userId}`);
  }

  async getKGGraph(options: { userId?: number; depth?: number; center?: string; maxNodes?: number } = {}): Promise<KGGraph> {
    const { userId = 1, depth = 3, center, maxNodes = 200 } = options;
    const params = new URLSearchParams({
      user_id: String(userId),
      depth: String(depth),
      max_nodes: String(maxNodes),
    });
    if (center) params.set('center', center);
    return this.request(`/api/v1/kg/graph?${params.toString()}`);
  }

  async getKGCommunities(userId = 1): Promise<KGCommunity[]> {
    return this.request(`/api/v1/kg/communities?user_id=${userId}`);
  }

  async getKGGaps(userId = 1, limit = 10): Promise<KGGapAnalysis> {
    return this.request(`/api/v1/kg/gaps?user_id=${userId}&limit=${limit}`);
  }

  async updateKGNode(nodeId: string, data: { mastery?: number; name?: string }, userId = 1): Promise<{ name: string; mastery?: number; updated: boolean }> {
    return this.request(`/api/v1/kg/node/${encodeURIComponent(nodeId)}?user_id=${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async createKGEdge(source: string, target: string, relation: string, userId = 1): Promise<{ id: string; source: string; target: string; relation: string; created: boolean }> {
    return this.request(`/api/v1/kg/edge?user_id=${userId}`, {
      method: 'POST',
      body: JSON.stringify({ source, target, relation }),
    });
  }

  async deleteKGEdge(edgeId: string, userId = 1): Promise<{ deleted: boolean; edge_id: string }> {
    return this.request(`/api/v1/kg/edge/${encodeURIComponent(edgeId)}?user_id=${userId}`, {
      method: 'DELETE',
    });
  }
}

export const apiClient = new AliceApiClient();
