'use client';

import { Search, Maximize2, SlidersHorizontal, Thermometer, LayoutGrid, Circle, Target } from 'lucide-react';
import { useState, useCallback, type ChangeEvent, useRef, useEffect } from 'react';
import type { KGCommunity } from '@/lib/types';

export type LayoutType = 'force' | 'hierarchical' | 'radial';

export interface GraphFilters {
    communityId: number | null;
    masteryRange: [number, number];
    conceptType: string | null;
    searchQuery: string;
}

interface GraphControlsProps {
    communities: KGCommunity[];
    filters: GraphFilters;
    onFiltersChange: (filters: GraphFilters) => void;
    layout: LayoutType;
    onLayoutChange: (layout: LayoutType) => void;
    heatmapMode: boolean;
    onHeatmapToggle: () => void;
    onFitView: () => void;
    onSearch: (query: string) => void;
}

const CONCEPT_TYPES = ['Concept', 'Method', 'Tool', 'Theory'];
const TYPE_LABELS_ZH: Record<string, string> = {
    Concept: '概念',
    Method: '方法',
    Tool: '工具',
    Theory: '理论',
};

const LAYOUT_CONFIG: { key: LayoutType; label: string; icon: typeof LayoutGrid }[] = [
    { key: 'force', label: '力导向', icon: Circle },
    { key: 'hierarchical', label: '层级', icon: LayoutGrid },
    { key: 'radial', label: '径向', icon: Target },
];

export function GraphControls({
    communities,
    filters,
    onFiltersChange,
    layout,
    onLayoutChange,
    heatmapMode,
    onHeatmapToggle,
    onFitView,
    onSearch,
}: GraphControlsProps) {
    const [showFilters, setShowFilters] = useState(false);
    const [searchFocused, setSearchFocused] = useState(false);
    const searchRef = useRef<HTMLInputElement>(null);

    // Close filters on Escape
    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') setShowFilters(false);
            // Ctrl+F / Cmd+F to focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                searchRef.current?.focus();
            }
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, []);

    const handleSearchChange = useCallback(
        (e: ChangeEvent<HTMLInputElement>) => {
            const query = e.target.value;
            onFiltersChange({ ...filters, searchQuery: query });
            onSearch(query);
        },
        [filters, onFiltersChange, onSearch],
    );

    const handleCommunityChange = useCallback(
        (e: ChangeEvent<HTMLSelectElement>) => {
            const val = e.target.value;
            onFiltersChange({
                ...filters,
                communityId: val === '' ? null : Number(val),
            });
        },
        [filters, onFiltersChange],
    );

    const handleTypeChange = useCallback(
        (e: ChangeEvent<HTMLSelectElement>) => {
            const val = e.target.value;
            onFiltersChange({
                ...filters,
                conceptType: val === '' ? null : val,
            });
        },
        [filters, onFiltersChange],
    );

    const handleMasteryMin = useCallback(
        (e: ChangeEvent<HTMLInputElement>) => {
            onFiltersChange({
                ...filters,
                masteryRange: [Number(e.target.value), filters.masteryRange[1]],
            });
        },
        [filters, onFiltersChange],
    );

    const handleMasteryMax = useCallback(
        (e: ChangeEvent<HTMLInputElement>) => {
            onFiltersChange({
                ...filters,
                masteryRange: [filters.masteryRange[0], Number(e.target.value)],
            });
        },
        [filters, onFiltersChange],
    );

    const hasActiveFilters = filters.communityId !== null || filters.conceptType !== null
        || filters.masteryRange[0] > 0 || filters.masteryRange[1] < 1;

    const clearFilters = useCallback(() => {
        onFiltersChange({
            communityId: null,
            masteryRange: [0, 1],
            conceptType: null,
            searchQuery: filters.searchQuery,
        });
    }, [filters.searchQuery, onFiltersChange]);

    return (
        <div className="graph-controls absolute top-4 left-4 z-10 flex flex-col gap-2 max-w-[240px]" data-testid="graph-controls">
            {/* Search bar */}
            <div className={`
                flex items-center gap-2 rounded-xl bg-card/90 backdrop-blur-sm border shadow-lg px-3 py-2
                transition-all duration-200
                ${searchFocused ? 'border-primary/50 ring-2 ring-primary/20' : 'border-border/50'}
            `}>
                <Search className="h-4 w-4 text-muted-foreground shrink-0" />
                <input
                    ref={searchRef}
                    type="text"
                    placeholder="搜索概念... (Ctrl+F)"
                    value={filters.searchQuery}
                    onChange={handleSearchChange}
                    onFocus={() => setSearchFocused(true)}
                    onBlur={() => setSearchFocused(false)}
                    className="bg-transparent text-sm outline-none placeholder:text-muted-foreground/60 w-full"
                    data-testid="graph-search"
                />
                {filters.searchQuery && (
                    <button
                        onClick={() => {
                            onFiltersChange({ ...filters, searchQuery: '' });
                            searchRef.current?.focus();
                        }}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                )}
            </div>

            {/* Tool bar */}
            <div className="flex gap-1.5">
                <button
                    onClick={onFitView}
                    className="rounded-xl bg-card/90 backdrop-blur-sm border border-border/50 shadow-lg p-2.5
                               hover:bg-accent/80 transition-all duration-200 hover:scale-105 active:scale-95"
                    title="适应画布"
                    data-testid="fit-view-btn"
                >
                    <Maximize2 className="h-4 w-4" />
                </button>

                <button
                    onClick={onHeatmapToggle}
                    className={`rounded-xl border shadow-lg p-2.5 transition-all duration-200 hover:scale-105 active:scale-95 backdrop-blur-sm ${
                        heatmapMode
                            ? 'bg-primary text-primary-foreground border-primary/50 shadow-primary/20'
                            : 'bg-card/90 border-border/50 hover:bg-accent/80'
                    }`}
                    title="掌握度热力图"
                    data-testid="heatmap-toggle"
                >
                    <Thermometer className="h-4 w-4" />
                </button>

                <button
                    onClick={() => setShowFilters(!showFilters)}
                    className={`rounded-xl border shadow-lg p-2.5 transition-all duration-200 hover:scale-105 active:scale-95 backdrop-blur-sm relative ${
                        showFilters
                            ? 'bg-primary text-primary-foreground border-primary/50 shadow-primary/20'
                            : 'bg-card/90 border-border/50 hover:bg-accent/80'
                    }`}
                    title="过滤器"
                    data-testid="filter-toggle"
                >
                    <SlidersHorizontal className="h-4 w-4" />
                    {hasActiveFilters && !showFilters && (
                        <div className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-primary border-2 border-card" />
                    )}
                </button>
            </div>

            {/* Layout selector */}
            <div className="rounded-xl bg-card/90 backdrop-blur-sm border border-border/50 shadow-lg px-3 py-2.5">
                <label className="text-[11px] font-medium text-muted-foreground mb-1.5 block uppercase tracking-wider">布局</label>
                <div className="flex gap-1">
                    {LAYOUT_CONFIG.map(({ key, label, icon: Icon }) => (
                        <button
                            key={key}
                            onClick={() => onLayoutChange(key)}
                            className={`flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 ${
                                layout === key
                                    ? 'bg-primary text-primary-foreground shadow-sm'
                                    : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                            }`}
                            data-testid={`layout-${key}`}
                        >
                            <Icon className="h-3 w-3" />
                            {label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Expandable filters panel */}
            {showFilters && (
                <div className="rounded-xl bg-card/90 backdrop-blur-sm border border-border/50 shadow-lg px-3.5 py-3.5 space-y-3.5 w-56 animate-in fade-in slide-in-from-top-2 duration-200" data-testid="filter-panel">
                    <div className="flex items-center justify-between">
                        <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">过滤条件</span>
                        {hasActiveFilters && (
                            <button
                                onClick={clearFilters}
                                className="text-[11px] text-primary hover:text-primary/80 font-medium transition-colors"
                            >
                                清除
                            </button>
                        )}
                    </div>

                    {/* Community filter */}
                    <div>
                        <label className="text-xs text-muted-foreground mb-1 block font-medium">社区</label>
                        <select
                            value={filters.communityId ?? ''}
                            onChange={handleCommunityChange}
                            className="w-full rounded-lg border border-border/50 bg-background/80 px-2.5 py-1.5 text-xs
                                       focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50 transition-all"
                            data-testid="community-filter"
                        >
                            <option value="">全部社区</option>
                            {communities.map((c) => (
                                <option key={c.community_id} value={c.community_id}>
                                    {c.label} ({c.concept_count})
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Type filter */}
                    <div>
                        <label className="text-xs text-muted-foreground mb-1 block font-medium">类型</label>
                        <select
                            value={filters.conceptType ?? ''}
                            onChange={handleTypeChange}
                            className="w-full rounded-lg border border-border/50 bg-background/80 px-2.5 py-1.5 text-xs
                                       focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50 transition-all"
                            data-testid="type-filter"
                        >
                            <option value="">全部类型</option>
                            {CONCEPT_TYPES.map((t) => (
                                <option key={t} value={t}>
                                    {TYPE_LABELS_ZH[t] ?? t}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Mastery range */}
                    <div>
                        <label className="text-xs text-muted-foreground mb-1.5 block font-medium">
                            掌握度: <span className="text-foreground font-semibold">{Math.round(filters.masteryRange[0] * 100)}%</span>
                            {' – '}
                            <span className="text-foreground font-semibold">{Math.round(filters.masteryRange[1] * 100)}%</span>
                        </label>
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] text-muted-foreground w-6">低</span>
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    value={filters.masteryRange[0]}
                                    onChange={handleMasteryMin}
                                    className="flex-1 accent-primary"
                                    data-testid="mastery-min"
                                />
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] text-muted-foreground w-6">高</span>
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    value={filters.masteryRange[1]}
                                    onChange={handleMasteryMax}
                                    className="flex-1 accent-primary"
                                    data-testid="mastery-max"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
