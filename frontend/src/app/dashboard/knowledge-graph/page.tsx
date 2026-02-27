'use client';

import { KnowledgeGraph } from '@/components/graph';

export default function KnowledgeGraphPage() {
    return (
        <div className="flex h-[calc(100vh-2rem)] flex-col px-4 py-4">
            <div className="mb-4">
                <h1 className="text-2xl font-bold">知识图谱</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    交互式知识概念可视化
                </p>
            </div>
            <div className="flex-1 rounded-lg border bg-card shadow-sm overflow-hidden">
                <KnowledgeGraph />
            </div>
        </div>
    );
}
