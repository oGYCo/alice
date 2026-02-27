'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import type { WeeklyVelocity } from '@/lib/types';

interface LearningVelocityProps {
    data: WeeklyVelocity[];
}

export function LearningVelocity({ data }: LearningVelocityProps) {
    const chartData = data.map((d) => ({
        week: d.week.replace(/^\d{4}-/, ''),
        count: d.count,
    }));

    return (
        <div className="learning-velocity rounded-lg border bg-card p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-muted-foreground">学习速度</h3>
            <p className="mb-2 text-xs text-muted-foreground">每周阅读量趋势（最近 8 周）</p>
            {chartData.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">暂无数据</p>
            ) : (
                <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                            <XAxis dataKey="week" tick={{ fontSize: 11 }} className="text-muted-foreground" />
                            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} className="text-muted-foreground" />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: 'hsl(var(--card))',
                                    border: '1px solid hsl(var(--border))',
                                    borderRadius: '6px',
                                    fontSize: '12px',
                                }}
                                labelStyle={{ color: 'hsl(var(--foreground))' }}
                            />
                            <Line
                                type="monotone"
                                dataKey="count"
                                stroke="hsl(var(--primary))"
                                strokeWidth={2}
                                dot={{ r: 3 }}
                                activeDot={{ r: 5 }}
                                name="阅读量"
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}
        </div>
    );
}
