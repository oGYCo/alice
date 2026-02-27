'use client';

import type { MemoryTierStats } from '@/lib/types';

interface MemoryOverviewProps {
    data: MemoryTierStats;
}

const tiers = [
    {
        key: 'working' as const,
        label: '工作记忆',
        description: '当前关注主题',
        color: 'bg-red-500',
        bgColor: 'bg-red-100 dark:bg-red-950',
    },
    {
        key: 'short_term' as const,
        label: '短期记忆',
        description: '近期阅读主题',
        color: 'bg-amber-500',
        bgColor: 'bg-amber-100 dark:bg-amber-950',
    },
    {
        key: 'long_term' as const,
        label: '长期记忆',
        description: '已掌握概念',
        color: 'bg-green-500',
        bgColor: 'bg-green-100 dark:bg-green-950',
    },
];

export function MemoryOverview({ data }: MemoryOverviewProps) {
    const total = data.working + data.short_term + data.long_term;

    return (
        <div className="memory-overview rounded-lg border bg-card p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-muted-foreground">记忆层级</h3>
            <p className="mb-3 text-xs text-muted-foreground">三层记忆系统概览</p>
            <div className="space-y-3">
                {tiers.map((tier) => {
                    const count = data[tier.key];
                    const pct = total > 0 ? (count / total) * 100 : 0;
                    return (
                        <div key={tier.key} className="memory-tier">
                            <div className="mb-1 flex items-center justify-between">
                                <span className="text-sm font-medium">{tier.label}</span>
                                <span className="text-sm font-semibold">{count}</span>
                            </div>
                            <div className="text-xs text-muted-foreground mb-1">{tier.description}</div>
                            <div className={`h-2 w-full rounded-full ${tier.bgColor}`}>
                                <div
                                    className={`h-full rounded-full transition-all ${tier.color}`}
                                    style={{ width: `${Math.max(pct, count > 0 ? 2 : 0)}%` }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>
            <div className="mt-3 text-center text-xs text-muted-foreground">
                总计 {total} 个记忆项
            </div>
        </div>
    );
}
