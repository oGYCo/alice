'use client';

import { useState } from 'react';
import type { KGGapSuggestion } from '@/lib/types';
import { Lightbulb, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';

interface GapAnalysisPanelProps {
    gaps: KGGapSuggestion[];
    totalGaps: number;
    onConceptClick: (concept: string) => void;
}

function getMasteryBadge(mastery: number): { bg: string; text: string } {
    if (mastery >= 0.3) return { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-600 dark:text-orange-400' };
    if (mastery > 0) return { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-600 dark:text-red-400' };
    return { bg: 'bg-muted/50', text: 'text-muted-foreground' };
}

export function GapAnalysisPanel({ gaps, totalGaps, onConceptClick }: GapAnalysisPanelProps) {
    const [expanded, setExpanded] = useState(true);

    if (gaps.length === 0) {
        return (
            <div className="gap-analysis-panel rounded-xl border border-border/50 bg-card/90 backdrop-blur-sm p-4 shadow-lg max-w-xs"
                 data-testid="gap-analysis">
                <div className="flex items-center gap-2 mb-2">
                    <div className="rounded-lg bg-yellow-100 dark:bg-yellow-900/30 p-1.5">
                        <Sparkles className="h-3.5 w-3.5 text-yellow-600 dark:text-yellow-400" />
                    </div>
                    <h3 className="text-sm font-semibold">推荐学习</h3>
                </div>
                <p className="text-xs text-muted-foreground/70 pl-9">暂无推荐（需更多知识图谱数据）</p>
            </div>
        );
    }

    return (
        <div className="gap-analysis-panel rounded-xl border border-border/50 bg-card/90 backdrop-blur-sm shadow-lg max-w-xs"
             data-testid="gap-analysis">
            {/* Header — clickable to collapse */}
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-accent/30 transition-colors rounded-t-xl"
            >
                <div className="flex items-center gap-2">
                    <div className="rounded-lg bg-yellow-100 dark:bg-yellow-900/30 p-1.5">
                        <Lightbulb className="h-3.5 w-3.5 text-yellow-600 dark:text-yellow-400" />
                    </div>
                    <h3 className="text-sm font-semibold">推荐学习</h3>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[11px] font-medium text-muted-foreground bg-muted/50 px-2 py-0.5 rounded-full">
                        {totalGaps}
                    </span>
                    {expanded ? (
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                        <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                </div>
            </button>

            {expanded && (
                <div className="px-3 pb-3 space-y-1.5 max-h-64 overflow-y-auto">
                    {gaps.map((gap, idx) => {
                        const masteryPct = Math.round(gap.mastery * 100);
                        const badge = getMasteryBadge(gap.mastery);
                        return (
                            <button
                                key={gap.concept}
                                onClick={() => onConceptClick(gap.concept)}
                                className="w-full rounded-lg bg-muted/20 hover:bg-accent/50 px-3 py-2.5 text-left
                                           transition-all duration-200 hover:shadow-sm group/gap"
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <div className="flex items-center gap-2 min-w-0">
                                        <span className="text-xs font-mono text-muted-foreground/50 w-4 shrink-0">
                                            {idx + 1}
                                        </span>
                                        <span className="text-sm font-medium truncate group-hover/gap:text-primary transition-colors">
                                            {gap.concept}
                                        </span>
                                    </div>
                                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0 ${badge.bg} ${badge.text}`}>
                                        {masteryPct}%
                                    </span>
                                </div>
                                {gap.reason && (
                                    <p className="text-[11px] text-muted-foreground/60 mt-1 ml-6 truncate">{gap.reason}</p>
                                )}
                                {gap.adjacent_mastered.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-1.5 ml-6">
                                        {gap.adjacent_mastered.slice(0, 3).map((adj) => (
                                            <span
                                                key={adj}
                                                className="rounded-md bg-green-100/80 dark:bg-green-900/20 px-1.5 py-0.5
                                                           text-[10px] text-green-700 dark:text-green-400 font-medium"
                                            >
                                                ✓ {adj}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
