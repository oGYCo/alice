'use client';

import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api';
import type { DashboardStats } from '@/lib/types';
import {
    LearningVelocity,
    KnowledgeGrowth,
    MemoryOverview,
    CommunityOverview,
    ReviewSchedule,
    ModeIndicator,
} from '@/components/dashboard';

function DashboardSkeleton() {
    return (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="animate-pulse rounded-lg border bg-card p-4 shadow-sm">
                    <div className="mb-3 h-4 w-24 rounded bg-muted" />
                    <div className="h-48 rounded bg-muted" />
                </div>
            ))}
        </div>
    );
}

function DashboardError({ message, onRetry }: { message: string; onRetry: () => void }) {
    return (
        <div className="flex flex-col items-center justify-center py-20 text-center">
            <p className="text-sm text-destructive mb-2">加载失败</p>
            <p className="text-xs text-muted-foreground mb-4">{message}</p>
            <button
                onClick={onRetry}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
                重试
            </button>
        </div>
    );
}

export default function DashboardPage() {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadStats = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await apiClient.getDashboardStats();
            setStats(data);
        } catch (err) {
            const msg = err instanceof Error ? err.message : '未知错误';
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadStats();
    }, []);

    return (
        <div className="mx-auto max-w-5xl px-4 py-6">
            <div className="mb-6">
                <h1 className="text-2xl font-bold">认知仪表盘</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    学习进展与知识概览
                </p>
            </div>

            {loading && <DashboardSkeleton />}
            {error && <DashboardError message={error} onRetry={loadStats} />}

            {stats && !loading && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <LearningVelocity data={stats.learning_velocity} />
                    <KnowledgeGrowth data={stats.knowledge_growth} />
                    <MemoryOverview data={stats.memory_tiers} />
                    <ReviewSchedule data={stats.review_schedule} />
                    <CommunityOverview data={stats.communities} />
                    <ModeIndicator data={stats.mode_info} />
                </div>
            )}
        </div>
    );
}
