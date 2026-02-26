import type { ContentItem, ContentDetail, Source, SearchResult, PushPreferences } from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export class AliceApiClient {
  private baseUrl: string;
  private apiKey: string | null;

  constructor(baseUrl = BASE_URL, apiKey: string | null = null) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(this.apiKey ? { 'X-API-Key': this.apiKey } : {}),
      ...(options.headers as Record<string, string> ?? {}),
    };
    const response = await fetch(`${this.baseUrl}${path}`, { ...options, headers });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw Object.assign(new Error(error.detail ?? response.statusText), { status: response.status });
    }
    return response.json() as Promise<T>;
  }

  async getContent(limit = 20, offset = 0): Promise<ContentItem[]> {
    return this.request(`/api/v1/content?limit=${limit}&offset=${offset}`);
  }

  async getContentDetail(id: number): Promise<ContentDetail> {
    return this.request(`/api/v1/content/${id}`);
  }

  async searchContent(q: string, limit = 20, offset = 0): Promise<SearchResult> {
    return this.request(`/api/v1/search?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`);
  }
  async getFeed(page = 1, limit = 20, sort = 'relevance'): Promise<ContentItem[]> {
    return this.request(`/api/v1/content?page=${page}&limit=${limit}&sort=${sort}`);
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

  async updatePushPreferences(userId: number, prefs: Partial<PushPreferences>): Promise<PushPreferences> {
    return this.request(`/api/v1/settings/push?user_id=${userId}`, {
      method: 'PUT',
      body: JSON.stringify(prefs),
    });
  }

  async healthCheck(): Promise<{ status: string }> {
    return this.request('/health');
  }
}

export const apiClient = new AliceApiClient();
