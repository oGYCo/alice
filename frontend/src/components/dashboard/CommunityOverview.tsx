'use client';

import type { CommunityInfo } from '@/lib/types';

interface CommunityOverviewProps {
    data: CommunityInfo[];
}

// Color palette for community clusters
const COMMUNITY_COLORS = [
    'bg-blue-500',
    'bg-purple-500',
    'bg-teal-500',
    'bg-orange-500',
    'bg-pink-500',
    'bg-indigo-500',
    'bg-cyan-500',
    'bg-emerald-500',
];

export function CommunityOverview({ data }: CommunityOverviewProps) {
    if (data.length === 0) {
        return (
            <div className="community-overview rounded-lg border bg-card p-4 shadow-sm">
                <h3 className="mb-3 text-sm font-semibold text-muted-foreground">知识社区</h3>
                <p className="py-8 text-center text-sm text-muted-foreground">
                    暂无社区数据（需要知识图谱数据）
                </p>
            </div>
        );
    }

    const maxConcepts = Math.max(...data.map((c) => c.concept_count), 1);

    return (
        <div className="community-overview rounded-lg border bg-card p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-muted-foreground">知识社区</h3>
            <p className="mb-3 text-xs text-muted-foreground">知识图谱聚类分布</p>
            <div className="space-y-3">
                {data.map((community, idx) => {
                    const color = COMMUNITY_COLORS[idx % COMMUNITY_COLORS.length];
                    const barWidth = (community.concept_count / maxConcepts) * 100;
                    const masteryPct = Math.round(community.avg_mastery * 100);

                    return (
                        <div key={community.community_id} className="community-cluster">
                            <div className="mb-1 flex items-center gap-2">
                                <div className={`h-3 w-3 rounded-full ${color}`} />
                                <span className="text-sm font-medium truncate flex-1">
                                    {community.label}
                                </span>
                                <span className="text-xs text-muted-foreground whitespace-nowrap">
                                    {community.concept_count} 概念 · {masteryPct}% 掌握
                                </span>
                            </div>
                            <div className="h-1.5 w-full rounded-full bg-muted">
                                <div
                                    className={`h-full rounded-full ${color} opacity-70 transition-all`}
                                    style={{ width: `${barWidth}%` }}
                                />
                            </div>
                            {community.top_concepts.length > 0 && (
                                <div className="mt-1 flex flex-wrap gap-1">
                                    {community.top_concepts.slice(0, 3).map((concept) => (
                                        <span
                                            key={concept}
                                            className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground"
                                        >
                                            {concept}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
