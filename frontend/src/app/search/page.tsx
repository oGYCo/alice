'use client';

import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Search, X, SlidersHorizontal, Clock, ExternalLink, Loader2, AlertCircle } from 'lucide-react';
import { apiClient } from '@/lib/api';
import type { SearchHit } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

// ── Constants ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 15;
const DEBOUNCE_MS = 320;

const CONTENT_TYPE_OPTIONS = [
    { value: '', label: '全部类型' },
    { value: 'knowledge', label: '硬核知识' },
    { value: 'thought', label: '思想性' },
    { value: 'news', label: '时效信息' },
];

const MIN_SCORE_OPTIONS = [
    { value: undefined, label: '不限质量' },
    { value: 6, label: '≥ 6 分' },
    { value: 7, label: '≥ 7 分' },
    { value: 8, label: '≥ 8 分' },
    { value: 9, label: '≥ 9 分' },
];

const CONTENT_TYPE_COLORS: Record<string, string> = {
    knowledge: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
    thought: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
    news: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
    time_sensitive: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
};

const CONTENT_TYPE_LABELS: Record<string, string> = {
    knowledge: '硬核知识',
    thought: '思想性',
    news: '时效信息',
    time_sensitive: '时效信息',
};

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Render Meilisearch <em>…</em> highlights safely, without dangerouslySetInnerHTML */
function HighlightedText({ html, fallback = '' }: { html?: string; fallback?: string }) {
    const text = html ?? fallback;
    if (!text) return null;

    // Split on <em>…</em> and alternate plain/bold segments
    const parts = text.split(/(<em>.*?<\/em>)/g);
    return (
        <>
            {parts.map((part, i) => {
                if (part.startsWith('<em>') && part.endsWith('</em>')) {
                    return (
                        <mark key={i} className="bg-yellow-200 dark:bg-yellow-800/50 text-foreground rounded-sm px-0">
                            {part.slice(4, -5)}
                        </mark>
                    );
                }
                return <span key={i}>{part}</span>;
            })}
        </>
    );
}

function formatTimeAgo(dateString: string) {
    const date = new Date(dateString);
    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 60) return '刚刚';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} 分钟前`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} 小时前`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days} 天前`;
    return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' });
}

// ── Search Result Card ────────────────────────────────────────────────────────

function SearchResultCard({ hit }: { hit: SearchHit }) {
    const typeLabel = hit.content_type ? CONTENT_TYPE_LABELS[hit.content_type] ?? hit.content_type : null;
    const typeColor = hit.content_type ? CONTENT_TYPE_COLORS[hit.content_type] ?? 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300' : '';

    return (
        <article className="group border-b border-border last:border-0 py-5 first:pt-0">
            {/* Top row: type badge · source · time */}
            <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground">
                {typeLabel && (
                    <span className={cn('px-2 py-0.5 rounded-full font-medium', typeColor)}>
                        {typeLabel}
                    </span>
                )}
                <span>{hit.source}</span>
                <span>·</span>
                <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatTimeAgo(hit.created_at)}
                </span>
                {hit.quality_score !== null && (
                    <>
                        <span>·</span>
                        <span>质量分 <strong className="text-foreground">{hit.quality_score}</strong></span>
                    </>
                )}
            </div>

            {/* Title */}
            <Link href={`/content/${hit.id}`} className="block group/link">
                <h2 className="font-semibold text-[16px] leading-snug mb-1.5 group-hover/link:text-primary transition-colors">
                    <HighlightedText html={hit._formatted?.title} fallback={hit.title} />
                </h2>
            </Link>

            {/* Summary */}
            {(hit._formatted?.summary ?? hit.summary) && (
                <p className="text-sm text-muted-foreground leading-relaxed line-clamp-2 mb-2">
                    <HighlightedText html={hit._formatted?.summary ?? undefined} fallback={hit.summary ?? ''} />
                </p>
            )}

            {/* Key points snippet (first matched key point if highlighted) */}
            {hit._formatted?.key_points && hit._formatted.key_points.some(kp => kp.includes('<em>')) && (
                <p className="text-xs text-muted-foreground border-l-2 border-primary/30 pl-2 italic mt-1">
                    <HighlightedText
                        html={hit._formatted.key_points.find(kp => kp.includes('<em>')) ?? hit._formatted.key_points[0]}
                    />
                </p>
            )}

            {/* Source link */}
            {hit.source_url && (
                <a
                    href={hit.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors truncate max-w-xs"
                >
                    <ExternalLink className="w-3 h-3 shrink-0" />
                    <span className="truncate">{hit.source_url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}</span>
                </a>
            )}
        </article>
    );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function SearchInner() {
    const router = useRouter();
    const searchParams = useSearchParams();

    // State derived from URL params
    const initialQ = searchParams.get('q') ?? '';
    const initialType = searchParams.get('type') ?? '';
    const initialMinScore = searchParams.get('min_score') ? Number(searchParams.get('min_score')) : undefined;

    const [inputValue, setInputValue] = useState(initialQ);
    const [activeQuery, setActiveQuery] = useState(initialQ);
    const [selectedType, setSelectedType] = useState(initialType);
    const [selectedMinScore, setSelectedMinScore] = useState<number | undefined>(initialMinScore);
    const [showFilters, setShowFilters] = useState(!!(initialType || initialMinScore));

    const [hits, setHits] = useState<SearchHit[]>([]);
    const [total, setTotal] = useState(0);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(false);
    const [loadingMore, setLoadingMore] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [hasSearched, setHasSearched] = useState(!!initialQ);

    const [suggestions, setSuggestions] = useState<string[]>([]);
    const [showSuggestions, setShowSuggestions] = useState(false);

    const inputRef = useRef<HTMLInputElement>(null);
    const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const suggestDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const suggestionsRef = useRef<HTMLUListElement>(null);

    // ── Sync URL ────────────────────────────────────────────────────────────────
    const updateURL = useCallback((q: string, type: string, minScore: number | undefined) => {
        const params = new URLSearchParams();
        if (q) params.set('q', q);
        if (type) params.set('type', type);
        if (minScore !== undefined) params.set('min_score', String(minScore));
        const qs = params.toString();
        router.replace(`/search${qs ? `?${qs}` : ''}`, { scroll: false });
    }, [router]);

    // ── Run search ──────────────────────────────────────────────────────────────
    const runSearch = useCallback(async (
        q: string,
        type: string,
        minScore: number | undefined,
        searchOffset: number,
        append = false,
    ) => {
        if (!q.trim()) {
            setHits([]);
            setTotal(0);
            setOffset(0);
            setHasSearched(false);
            return;
        }
        if (append) setLoadingMore(true); else setLoading(true);
        setError(null);
        try {
            const result = await apiClient.searchContent(q, {
                limit: PAGE_SIZE,
                offset: searchOffset,
                type: type || undefined,
                min_score: minScore,
            });
            if (append) {
                setHits(prev => [...prev, ...result.hits]);
            } else {
                setHits(result.hits);
            }
            setTotal(result.total);
            setOffset(searchOffset);
            setHasSearched(true);
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Search failed';
            setError(msg);
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    }, []);

    // ── Debounced input handler ─────────────────────────────────────────────────
    const handleInputChange = (value: string) => {
        setInputValue(value);

        // Suggestions debounce — 200ms
        if (suggestDebounceRef.current) clearTimeout(suggestDebounceRef.current);
        if (value.trim().length >= 2) {
            suggestDebounceRef.current = setTimeout(async () => {
                try {
                    const s = await apiClient.getSuggestions(value, 6);
                    setSuggestions(s);
                    setShowSuggestions(s.length > 0);
                } catch {
                    setSuggestions([]);
                }
            }, 200);
        } else {
            setSuggestions([]);
            setShowSuggestions(false);
        }

        // Search debounce — 320ms
        if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = setTimeout(() => {
            const q = value.trim();
            setActiveQuery(q);
            updateURL(q, selectedType, selectedMinScore);
            runSearch(q, selectedType, selectedMinScore, 0, false);
        }, DEBOUNCE_MS);
    };

    // ── Apply suggestion ─────────────────────────────────────────────────────────
    const applySuggestion = (suggestion: string) => {
        if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
        setInputValue(suggestion);
        setActiveQuery(suggestion);
        setShowSuggestions(false);
        setSuggestions([]);
        updateURL(suggestion, selectedType, selectedMinScore);
        runSearch(suggestion, selectedType, selectedMinScore, 0, false);
    };

    // ── Clear search ─────────────────────────────────────────────────────────────
    const clearSearch = () => {
        if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
        setInputValue('');
        setActiveQuery('');
        setHits([]);
        setTotal(0);
        setHasSearched(false);
        setShowSuggestions(false);
        setSuggestions([]);
        updateURL('', selectedType, selectedMinScore);
        inputRef.current?.focus();
    };

    // ── Filter change ─────────────────────────────────────────────────────────────
    const handleFilterChange = (type: string, minScore: number | undefined) => {
        setSelectedType(type);
        setSelectedMinScore(minScore);
        if (activeQuery.trim()) {
            updateURL(activeQuery, type, minScore);
            runSearch(activeQuery, type, minScore, 0, false);
        } else {
            updateURL(inputValue.trim(), type, minScore);
        }
    };

    // ── Load more ────────────────────────────────────────────────────────────────
    const loadMore = () => {
        const nextOffset = offset + PAGE_SIZE;
        runSearch(activeQuery, selectedType, selectedMinScore, nextOffset, true);
    };

    // ── Keyboard — close suggestions on Escape ───────────────────────────────────
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') setShowSuggestions(false);
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, []);

    // ── Click outside suggestions ────────────────────────────────────────────────
    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (
                suggestionsRef.current &&
                !suggestionsRef.current.contains(e.target as Node) &&
                inputRef.current &&
                !inputRef.current.contains(e.target as Node)
            ) {
                setShowSuggestions(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, []);

    // ── Initial search if URL has query ──────────────────────────────────────────
    useEffect(() => {
        if (initialQ.trim()) {
            runSearch(initialQ, initialType, initialMinScore, 0, false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const hasMore = offset + PAGE_SIZE < total;

    // ── Render ───────────────────────────────────────────────────────────────────
    return (
        <div className="max-w-[720px] mx-auto px-5 py-10">
            {/* Page heading */}
            <h1 className="font-sans text-2xl font-semibold tracking-tight mb-7">搜索</h1>

            {/* Search input */}
            <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <Input
                    ref={inputRef}
                    value={inputValue}
                    placeholder="搜索标题、摘要、关键要点…"
                    className="pl-9 pr-10 h-11 text-sm font-sans"
                    onChange={e => handleInputChange(e.target.value)}
                    onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                    onKeyDown={e => {
                        if (e.key === 'Enter') {
                            if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
                            const q = inputValue.trim();
                            setActiveQuery(q);
                            setShowSuggestions(false);
                            updateURL(q, selectedType, selectedMinScore);
                            runSearch(q, selectedType, selectedMinScore, 0, false);
                        }
                    }}
                    autoComplete="off"
                    data-testid="search-input"
                />
                {inputValue && (
                    <button
                        onClick={clearSearch}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                        aria-label="Clear search"
                    >
                        <X className="h-4 w-4" />
                    </button>
                )}

                {/* Suggestions dropdown */}
                {showSuggestions && suggestions.length > 0 && (
                    <ul
                        ref={suggestionsRef}
                        className="absolute z-50 left-0 right-0 top-[calc(100%+4px)] bg-popover border border-border rounded-lg shadow-lg overflow-hidden"
                        role="listbox"
                    >
                        {suggestions.map((s, i) => (
                            <li key={i} role="option" aria-selected={false}>
                                <button
                                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-accent transition-colors flex items-center gap-2"
                                    onMouseDown={e => e.preventDefault()}   // prevent input blur
                                    onClick={() => applySuggestion(s)}
                                >
                                    <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                    {s}
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            {/* Filter bar */}
            <div className="flex items-center gap-2 mb-6">
                <Button
                    variant={showFilters ? 'secondary' : 'ghost'}
                    size="sm"
                    className="gap-1.5 h-8 text-xs"
                    onClick={() => setShowFilters(f => !f)}
                >
                    <SlidersHorizontal className="h-3.5 w-3.5" />
                    筛选
                    {(selectedType || selectedMinScore !== undefined) && (
                        <Badge variant="default" className="ml-0.5 h-4 px-1 text-[10px] font-semibold leading-none">
                            {[selectedType && '类型', selectedMinScore !== undefined && '分数'].filter(Boolean).length}
                        </Badge>
                    )}
                </Button>

                {/* Active filter chips */}
                {selectedType && (
                    <span className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium bg-secondary">
                        {CONTENT_TYPE_OPTIONS.find(o => o.value === selectedType)?.label ?? selectedType}
                        <button
                            onClick={() => handleFilterChange('', selectedMinScore)}
                            className="ml-0.5 hover:text-destructive"
                            aria-label="Remove type filter"
                        >
                            <X className="h-3 w-3" />
                        </button>
                    </span>
                )}
                {selectedMinScore !== undefined && (
                    <span className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium bg-secondary">
                        ≥ {selectedMinScore} 分
                        <button
                            onClick={() => handleFilterChange(selectedType, undefined)}
                            className="ml-0.5 hover:text-destructive"
                            aria-label="Remove score filter"
                        >
                            <X className="h-3 w-3" />
                        </button>
                    </span>
                )}
            </div>

            {/* Expanded filter panel */}
            {showFilters && (
                <div className="mb-6 p-4 rounded-xl border border-border bg-muted/40 space-y-4">
                    {/* Content type */}
                    <div>
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">内容类型</p>
                        <div className="flex flex-wrap gap-2">
                            {CONTENT_TYPE_OPTIONS.map(opt => (
                                <button
                                    key={opt.value}
                                    onClick={() => handleFilterChange(opt.value, selectedMinScore)}
                                    className={cn(
                                        'px-3 py-1 rounded-full text-sm border transition-colors',
                                        selectedType === opt.value
                                            ? 'bg-primary text-primary-foreground border-primary'
                                            : 'border-border hover:bg-accent'
                                    )}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Min quality score */}
                    <div>
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">最低质量分</p>
                        <div className="flex flex-wrap gap-2">
                            {MIN_SCORE_OPTIONS.map(opt => (
                                <button
                                    key={opt.value ?? 'none'}
                                    onClick={() => handleFilterChange(selectedType, opt.value)}
                                    className={cn(
                                        'px-3 py-1 rounded-full text-sm border transition-colors',
                                        selectedMinScore === opt.value
                                            ? 'bg-primary text-primary-foreground border-primary'
                                            : 'border-border hover:bg-accent'
                                    )}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* Error */}
            {error && (
                <div className="flex items-start gap-3 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive mb-6">
                    <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                    <span>{error}</span>
                </div>
            )}

            {/* Loading skeleton */}
            {loading && (
                <div className="flex items-center justify-center py-16 text-muted-foreground gap-2">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-sm">搜索中…</span>
                </div>
            )}

            {/* Results */}
            {!loading && hasSearched && (
                <>
                    {/* Result count */}
                    <p className="text-xs text-muted-foreground mb-4">
                        {total === 0
                            ? `未找到与 "${activeQuery}" 相关的结果`
                            : `找到约 ${total} 条结果，显示 ${hits.length} 条`
                        }
                    </p>

                    {/* Hit list */}
                    {hits.length > 0 && (
                        <div className="divide-y divide-border rounded-xl border border-border px-5">
                            {hits.map(hit => (
                                <SearchResultCard key={hit.id} hit={hit} />
                            ))}
                        </div>
                    )}

                    {/* Load more */}
                    {hasMore && (
                        <div className="mt-6 text-center">
                            <Button
                                variant="outline"
                                onClick={loadMore}
                                disabled={loadingMore}
                                className="gap-2"
                            >
                                {loadingMore ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        加载中…
                                    </>
                                ) : (
                                    `加载更多（剩余约 ${total - hits.length} 条）`
                                )}
                            </Button>
                        </div>
                    )}

                    {/* Empty state */}
                    {total === 0 && (
                        <div className="py-16 text-center">
                            <Search className="h-10 w-10 text-muted-foreground/30 mx-auto mb-4" />
                            <p className="text-base font-medium text-muted-foreground mb-1">没有找到相关内容</p>
                            <p className="text-sm text-muted-foreground/70">
                                尝试不同的关键词，或{' '}
                                {(selectedType || selectedMinScore !== undefined) && (
                                    <button
                                        onClick={() => handleFilterChange('', undefined)}
                                        className="text-primary underline underline-offset-2"
                                    >
                                        移除筛选条件
                                    </button>
                                )}
                            </p>
                        </div>
                    )}
                </>
            )}

            {/* Initial state — not yet searched */}
            {!loading && !hasSearched && !error && (
                <div className="py-16 text-center">
                    <Search className="h-12 w-12 text-muted-foreground/20 mx-auto mb-5" />
                    <p className="text-base text-muted-foreground">
                        在上方输入关键词搜索所有已索引内容
                    </p>
                    <p className="text-sm text-muted-foreground/60 mt-1">
                        支持搜索标题、AI 概括、关键要点
                    </p>
                </div>
            )}
        </div>
    );
}

/**
 * Next.js 14 App Router requires `useSearchParams` to be wrapped in a
 * Suspense boundary when used inside a Client Component page.
 */
export default function SearchPage() {
    return (
        <Suspense
            fallback={
                <div className="max-w-[720px] mx-auto px-5 py-10 flex items-center justify-center gap-2 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-sm">加载搜索页面…</span>
                </div>
            }
        >
            <SearchInner />
        </Suspense>
    );
}
