// Content types
export interface ContentItem {
  id: number;
  title: string;
  url: string;
  summary: string | null;
  source: string;
  source_url: string;
  content_type: string | null;
  quality_score: number | null;
  p_score: number | null;
  pipeline_status: string;
  created_at: string;
  published_at: string | null;
  pushed_at: string | null;
  metadata_: Record<string, unknown> | null;
}

export interface Source {
  id: number;
  name: string;
  url: string;
  type: string;
  is_active: boolean;
  created_at: string;
}

export interface Feedback {
  id: number;
  content_id: number;
  user_id: number;
  type: string;
  created_at: string;
}

export interface SearchResult {
  hits: ContentItem[];
  total: number;
  limit: number;
  offset: number;
  facets: Record<string, Record<string, number>>;
}

export interface PushPreferences {
  user_id: number;
  quiet_start: number;
  quiet_end: number;
  max_per_day: number;
  preferred_types: string[];
}

export interface ApiError {
  detail: string;
  status: number;
}
