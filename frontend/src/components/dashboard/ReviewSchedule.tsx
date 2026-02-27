'use client';

import { Calendar, Flame, BookOpen, RotateCcw } from 'lucide-react';
import type { ReviewScheduleStats } from '@/lib/types';

interface ReviewScheduleProps {
    data: ReviewScheduleStats;
}

export function ReviewSchedule({ data }: ReviewScheduleProps) {
    const stateLabels: Record<string, string> = {
        new: '新卡片',
        learning: '学习中',
        review: '复习中',
        relearning: '重新学习',
    };

    return (
        <div className="review-schedule rounded-lg border bg-card p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-muted-foreground">复习计划</h3>
            <p className="mb-3 text-xs text-muted-foreground">FSRS 间隔重复进度</p>

            <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="flex items-center gap-2 rounded-md bg-muted/50 p-3">
                    <Calendar className="h-4 w-4 text-primary" />
                    <div>
                        <p className="text-lg font-bold leading-none">{data.due_today}</p>
                        <p className="text-[10px] text-muted-foreground mt-0.5">今日待复习</p>
                    </div>
                </div>
                <div className="flex items-center gap-2 rounded-md bg-muted/50 p-3">
                    <BookOpen className="h-4 w-4 text-primary" />
                    <div>
                        <p className="text-lg font-bold leading-none">{data.due_this_week}</p>
                        <p className="text-[10px] text-muted-foreground mt-0.5">本周待复习</p>
                    </div>
                </div>
                <div className="flex items-center gap-2 rounded-md bg-muted/50 p-3">
                    <RotateCcw className="h-4 w-4 text-primary" />
                    <div>
                        <p className="text-lg font-bold leading-none">{data.total_cards}</p>
                        <p className="text-[10px] text-muted-foreground mt-0.5">卡片总数</p>
                    </div>
                </div>
                <div className="flex items-center gap-2 rounded-md bg-muted/50 p-3">
                    <Flame className="h-4 w-4 text-orange-500" />
                    <div>
                        <p className="text-lg font-bold leading-none">{data.streak_days}</p>
                        <p className="text-[10px] text-muted-foreground mt-0.5">连续天数</p>
                    </div>
                </div>
            </div>

            {Object.keys(data.cards_by_state).length > 0 && (
                <div>
                    <p className="text-xs font-medium text-muted-foreground mb-2">卡片状态分布</p>
                    <div className="flex gap-2">
                        {Object.entries(data.cards_by_state).map(([state, count]) => (
                            <div
                                key={state}
                                className="flex-1 rounded-md bg-muted/50 p-2 text-center"
                            >
                                <p className="text-sm font-semibold">{count}</p>
                                <p className="text-[10px] text-muted-foreground">
                                    {stateLabels[state] ?? state}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
