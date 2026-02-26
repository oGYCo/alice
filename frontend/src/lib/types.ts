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

export interface ContentSubgraph {
  nodes: Array<{
    id: string;
    label: string;
    mastery: number; // 0-1 (e.g. 0.0=unknown, 0.5=partial, 1.0=mastered)
  }>;
  edges: Array<{
    from: string;
    to: string;
    relation: string;
  }>;
}

export interface ContentDetail extends ContentItem {
  key_takeaways: string[] | null;
  push_reason: string | null;
  reading_suggestion: string | null;
  full_content: string | null;
  subgraph: ContentSubgraph | null;
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

export type UserMode = 'daily' | 'project' | 'explore' | 'low_energy';

export type ScheduleSlotName = 'morning' | 'work' | 'lunch' | 'evening' | 'late_night' | 'weekend';

export interface ScheduleSlot {
  name: ScheduleSlotName;
  start_time: string;
  end_time: string;
  is_enabled: boolean;
  max_pushes: number;
}

export interface PushPreferences {
  user_id: number;
  quiet_start: number;
  quiet_end: number;
  max_per_day: number;
  preferred_types: string[];
  epsilon: number;
  user_mode: UserMode;
  project_description?: string;
  schedule?: Record<ScheduleSlotName, ScheduleSlot>;
  type_weights?: Record<string, number>;
}

export interface ApiError {
  detail: string;
  status: number;
}
