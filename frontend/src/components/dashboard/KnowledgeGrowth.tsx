'use client';

import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from 'recharts';
import type { KnowledgeGrowthPoint } from '@/lib/types';

interface KnowledgeGrowthProps {
    data: KnowledgeGrowthPoint[];
}

export function KnowledgeGrowth({ data }: KnowledgeGrowthProps) {
    const chartData = data.map((d) => ({
        week: d.week.replace(/^\d{4}-/, ''),
        total: d.total_nodes,
        new: d.new_nodes,
        mastered: d.mastered_nodes,
    }));

    return (
        <div className="knowledge-growth rounded-lg border bg-card p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-muted-foreground">知识增长</h3>
            <p className="mb-2 text-xs text-muted-foreground">知识图谱节点变化</p>
            {chartData.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">暂无数据</p>
            ) : (
                <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                            <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: 'hsl(var(--card))',
                                    border: '1px solid hsl(var(--border))',
                                    borderRadius: '6px',
                                    fontSize: '12px',
                                }}
                            />
                            <Legend wrapperStyle={{ fontSize: '11px' }} />
                            <Bar dataKey="new" name="新增" fill="hsl(var(--primary))" radius={[2, 2, 0, 0]} />
                            <Bar dataKey="mastered" name="已掌握" fill="hsl(142, 71%, 45%)" radius={[2, 2, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}
        </div>
    );
}
