'use client';

import type { KGGapSuggestion } from '@/lib/types';
import { Lightbulb } from 'lucide-react';

interface GapAnalysisPanelProps {
    gaps: KGGapSuggestion[];
    totalGaps: number;
    onConceptClick: (concept: string) => void;
}

export function GapAnalysisPanel({ gaps, totalGaps, onConceptClick }: GapAnalysisPanelProps) {
    if (gaps.length === 0) {
        return (
            <div className="gap-analysis-panel rounded-lg border bg-card p-4 shadow-sm" data-testid="gap-analysis">
                <div className="flex items-center gap-2 mb-2">
                    <Lightbulb className="h-4 w-4 text-yellow-500" />
                    <h3 className="text-sm font-semibold">推荐学习</h3>
                </div>
                <p className="text-xs text-muted-foreground">暂无推荐（需要更多知识图谱数据）</p>
            </div>
        );
    }

    return (
        <div className="gap-analysis-panel rounded-lg border bg-card p-4 shadow-sm" data-testid="gap-analysis">
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-yellow-500" />
                    <h3 className="text-sm font-semibold">推荐学习</h3>
                </div>
                <span className="text-xs text-muted-foreground">{totalGaps} 个知识缺口</span>
            </div>

            <div className="space-y-2 max-h-60 overflow-y-auto">
                {gaps.map((gap) => {
                    const masteryPct = Math.round(gap.mastery * 100);
                    return (
                        <button
                            key={gap.concept}
                            onClick={() => onConceptClick(gap.concept)}
                            className="w-full rounded-lg bg-muted/30 px-3 py-2 text-left hover:bg-accent/50 transition-colors"
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-medium truncate">{gap.concept}</span>
                                <span className="text-xs text-muted-foreground shrink-0 ml-2">
                                    {masteryPct}%
                                </span>
                            </div>
                            {gap.reason && (
                                <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{gap.reason}</p>
                            )}
                            {gap.adjacent_mastered.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-1">
                                    {gap.adjacent_mastered.slice(0, 3).map((adj) => (
                                        <span
                                            key={adj}
                                            className="rounded bg-green-100 dark:bg-green-900/30 px-1.5 py-0.5 text-[10px] text-green-700 dark:text-green-300"
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
        </div>
    );
}
