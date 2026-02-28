'use client';

import { KnowledgeGraph } from '@/components/graph';

export default function KnowledgeGraphPage() {
    return (
        <div className="flex h-[calc(100vh-2rem)] flex-col px-4 py-4">
            <div className="mb-3 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">知识图谱</h1>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        可视化探索您的知识网络 · 点击节点查看详情
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-green-500" />掌握</span>
                        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-yellow-500" />学习中</span>
                        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-400" />未知</span>
                    </div>
                </div>
            </div>
            <div className="flex-1 rounded-xl border border-border/50 bg-card shadow-sm overflow-hidden">
                <KnowledgeGraph />
            </div>
        </div>
    );
}
