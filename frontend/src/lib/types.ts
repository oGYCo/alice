// Content types
export interface ContentItem {
  id: number;
  title: string;
  url?: string; // not returned by backend; source_url is the article URL
  summary: string | null;
  source: string;
  source_url: string; // normalized article URL (used for dedup in backend)
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
    name: string;    // display name of the concept
    label: string;   // Neo4j node label (Concept / Method / Tool / Theory)
    mastery: number; // 0-1 (e.g. 0.0=unknown, 0.5=partial, 1.0=mastered)
  }>;
  edges: Array<{
    from: string;
    to: string;
    relation: string;
  }>;
}

export interface ContentDetail extends ContentItem {
  key_points: string[] | null;
  domains: string[] | null;
  estimated_read_time: number | null;
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
  hits: SearchHit[];
  total: number;
  limit: number;
  offset: number;
  facets: Record<string, Record<string, number>>;
}

/**
 * A single Meilisearch search hit.
 * `id` comes back as a string from the index (we coerce it to number in the API layer).
 * `_formatted` contains the same fields but with <em>…</em> highlight tags around matches.
 */
export interface SearchHit {
  id: number;           // coerced from string at API layer
  title: string;
  summary: string | null;
  key_points: string[] | null;
  source: string;
  source_url: string;
  content_type: string | null;
  quality_score: number | null;
  p_score: number | null;
  pipeline_status: string;
  created_at: string;
  _formatted?: {
    title?: string;
    summary?: string;
    key_points?: string[];
  };
}

export interface HybridSearchHit {
  content_id: string;
  score: number;
  source: string;
  graph_score: number;
  text_score: number;
  semantic_score: number;
}

export interface HybridSearchResult {
  results: HybridSearchHit[];
  total: number;
  query: string;
  mode: string;
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

// Dashboard types
export interface WeeklyVelocity {
  week: string;
  count: number;
}

export interface KnowledgeGrowthPoint {
  week: string;
  total_nodes: number;
  new_nodes: number;
  mastered_nodes: number;
}

export interface MemoryTierStats {
  working: number;
  short_term: number;
  long_term: number;
}

export interface CommunityInfo {
  community_id: number;
  label: string;
  concept_count: number;
  avg_mastery: number;
  top_concepts: string[];
}

export interface ReviewScheduleStats {
  due_today: number;
  due_this_week: number;
  total_cards: number;
  streak_days: number;
  cards_by_state: Record<string, number>;
}

export interface ModeHistoryEntry {
  mode: string;
  timestamp: string | null;
}

export interface ModeInfo {
  current_mode: string;
  recent_history: ModeHistoryEntry[];
}

export interface DashboardStats {
  learning_velocity: WeeklyVelocity[];
  knowledge_growth: KnowledgeGrowthPoint[];
  memory_tiers: MemoryTierStats;
  communities: CommunityInfo[];
  review_schedule: ReviewScheduleStats;
  mode_info: ModeInfo;
}

// Knowledge Graph Visualization types
export interface KGNode {
  id: string;
  name: string;
  label: string; // Concept | Method | Tool | Theory
  mastery: number; // 0-1
  community_id: number | null;
  aliases: string[];
}

export interface KGEdge {
  id: string;
  source: string;
  target: string;
  label: string;
}

export interface KGGraph {
  nodes: KGNode[];
  edges: KGEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface KGCommunity {
  community_id: number;
  label: string;
  concept_count: number;
  avg_mastery: number;
  concepts: string[];
}

export interface KGGapSuggestion {
  concept: string;
  mastery: number;
  adjacent_mastered: string[];
  reason: string;
}

export interface KGGapAnalysis {
  gaps: KGGapSuggestion[];
  total_gaps: number;
}
