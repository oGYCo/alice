'use client';

import { Activity, Briefcase, Compass, Moon } from 'lucide-react';
import type { ModeInfo } from '@/lib/types';

interface ModeIndicatorProps {
    data: ModeInfo;
}

const modeConfig: Record<string, { label: string; icon: typeof Activity; color: string; description: string }> = {
    daily: {
        label: '日常模式',
        icon: Activity,
        color: 'text-blue-500',
        description: '平衡阅读，文章择优推送',
    },
    project: {
        label: '专注模式',
        icon: Briefcase,
        color: 'text-purple-500',
        description: '聚焦项目相关内容',
    },
    explore: {
        label: '探索模式',
        icon: Compass,
        color: 'text-teal-500',
        description: '发现跨领域内容',
    },
    low_energy: {
        label: '低能耗模式',
        icon: Moon,
        color: 'text-amber-500',
        description: '轻量内容，减少推送',
    },
};

export function ModeIndicator({ data }: ModeIndicatorProps) {
    const config = modeConfig[data.current_mode] ?? modeConfig.daily;
    const Icon = config.icon;

    return (
        <div className="mode-indicator rounded-lg border bg-card p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-muted-foreground">当前模式</h3>
            <div className="flex items-center gap-3">
                <div className={`rounded-full bg-muted p-2 ${config.color}`}>
                    <Icon className="h-5 w-5" />
                </div>
                <div>
                    <p className="font-semibold">{config.label}</p>
                    <p className="text-xs text-muted-foreground">{config.description}</p>
                </div>
            </div>
            {data.recent_history.length > 1 && (
                <div className="mt-3 border-t pt-2">
                    <p className="text-xs font-medium text-muted-foreground mb-1">最近切换</p>
                    <div className="flex gap-1">
                        {data.recent_history.slice(0, 5).map((entry, idx) => {
                            const entryConfig = modeConfig[entry.mode] ?? modeConfig.daily;
                            const EntryIcon = entryConfig.icon;
                            return (
                                <div
                                    key={idx}
                                    className={`rounded-full bg-muted p-1.5 ${entryConfig.color}`}
                                    title={entryConfig.label}
                                >
                                    <EntryIcon className="h-3 w-3" />
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
