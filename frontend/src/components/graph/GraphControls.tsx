'use client';

import { Search, Maximize2, SlidersHorizontal, Thermometer } from 'lucide-react';
import { useState, useCallback, type ChangeEvent } from 'react';
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

    return (
        <div className="graph-controls absolute top-4 left-4 z-10 flex flex-col gap-2" data-testid="graph-controls">
            {/* Search */}
            <div className="flex items-center gap-2 rounded-lg bg-card border shadow-sm px-3 py-2">
                <Search className="h-4 w-4 text-muted-foreground" />
                <input
                    type="text"
                    placeholder="搜索概念..."
                    value={filters.searchQuery}
                    onChange={handleSearchChange}
                    className="bg-transparent text-sm outline-none placeholder:text-muted-foreground w-40"
                    data-testid="graph-search"
                />
            </div>

            {/* Action buttons */}
            <div className="flex gap-1">
                <button
                    onClick={onFitView}
                    className="rounded-lg bg-card border shadow-sm p-2 hover:bg-accent transition-colors"
                    title="适应画布"
                    data-testid="fit-view-btn"
                >
                    <Maximize2 className="h-4 w-4" />
                </button>

                <button
                    onClick={onHeatmapToggle}
                    className={`rounded-lg border shadow-sm p-2 transition-colors ${heatmapMode ? 'bg-primary text-primary-foreground' : 'bg-card hover:bg-accent'
                        }`}
                    title="掌握度热力图"
                    data-testid="heatmap-toggle"
                >
                    <Thermometer className="h-4 w-4" />
                </button>

                <button
                    onClick={() => setShowFilters(!showFilters)}
                    className={`rounded-lg border shadow-sm p-2 transition-colors ${showFilters ? 'bg-primary text-primary-foreground' : 'bg-card hover:bg-accent'
                        }`}
                    title="过滤器"
                    data-testid="filter-toggle"
                >
                    <SlidersHorizontal className="h-4 w-4" />
                </button>
            </div>

            {/* Layout selector */}
            <div className="rounded-lg bg-card border shadow-sm px-3 py-2">
                <label className="text-xs text-muted-foreground mb-1 block">布局</label>
                <div className="flex gap-1">
                    {(['force', 'hierarchical', 'radial'] as const).map((l) => (
                        <button
                            key={l}
                            onClick={() => onLayoutChange(l)}
                            className={`px-2 py-1 text-xs rounded transition-colors ${layout === l
                                    ? 'bg-primary text-primary-foreground'
                                    : 'bg-muted hover:bg-accent'
                                }`}
                            data-testid={`layout-${l}`}
                        >
                            {l === 'force' ? '力导向' : l === 'hierarchical' ? '层级' : '径向'}
                        </button>
                    ))}
                </div>
            </div>

            {/* Expandable filters panel */}
            {showFilters && (
                <div className="rounded-lg bg-card border shadow-sm px-3 py-3 space-y-3 w-56" data-testid="filter-panel">
                    {/* Community filter */}
                    <div>
                        <label className="text-xs text-muted-foreground mb-1 block">社区</label>
                        <select
                            value={filters.communityId ?? ''}
                            onChange={handleCommunityChange}
                            className="w-full rounded border bg-background px-2 py-1 text-xs"
                            data-testid="community-filter"
                        >
                            <option value="">全部</option>
                            {communities.map((c) => (
                                <option key={c.community_id} value={c.community_id}>
                                    {c.label} ({c.concept_count})
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Type filter */}
                    <div>
                        <label className="text-xs text-muted-foreground mb-1 block">类型</label>
                        <select
                            value={filters.conceptType ?? ''}
                            onChange={handleTypeChange}
                            className="w-full rounded border bg-background px-2 py-1 text-xs"
                            data-testid="type-filter"
                        >
                            <option value="">全部</option>
                            {CONCEPT_TYPES.map((t) => (
                                <option key={t} value={t}>
                                    {t}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Mastery range */}
                    <div>
                        <label className="text-xs text-muted-foreground mb-1 block">
                            掌握度: {Math.round(filters.masteryRange[0] * 100)}% - {Math.round(filters.masteryRange[1] * 100)}%
                        </label>
                        <div className="flex items-center gap-2">
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.1"
                                value={filters.masteryRange[0]}
                                onChange={handleMasteryMin}
                                className="w-full"
                                data-testid="mastery-min"
                            />
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.1"
                                value={filters.masteryRange[1]}
                                onChange={handleMasteryMax}
                                className="w-full"
                                data-testid="mastery-max"
                            />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
