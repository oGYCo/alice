'use client';

import { useState, useCallback } from 'react';
import { X, Save, Trash2, GitMerge } from 'lucide-react';
import type { KGNode, KGEdge } from '@/lib/types';

interface NodeEditorProps {
    node: KGNode;
    edges: KGEdge[];
    onClose: () => void;
    onUpdateMastery: (nodeId: string, mastery: number) => void;
    onRenameNode: (nodeId: string, newName: string) => void;
    onDeleteEdge: (edgeId: string) => void;
    onCreateEdge: (source: string, target: string, relation: string) => void;
}

const RELATION_TYPES = [
    'PREREQUISITE_OF',
    'EXTENDS',
    'APPLIES_TO',
    'CONTRASTS',
];

export function NodeEditor({
    node,
    edges,
    onClose,
    onUpdateMastery,
    onRenameNode,
    onDeleteEdge,
    onCreateEdge,
}: NodeEditorProps) {
    const [mastery, setMastery] = useState(node.mastery);
    const [name, setName] = useState(node.name);
    const [newEdgeTarget, setNewEdgeTarget] = useState('');
    const [newEdgeRelation, setNewEdgeRelation] = useState(RELATION_TYPES[0]);
    const [saving, setSaving] = useState(false);

    // Edges connected to this node
    const connectedEdges = edges.filter(
        (e) => e.source === node.id || e.target === node.id,
    );

    const handleSaveMastery = useCallback(async () => {
        setSaving(true);
        try {
            onUpdateMastery(node.id, mastery);
        } finally {
            setSaving(false);
        }
    }, [node.id, mastery, onUpdateMastery]);

    const handleSaveName = useCallback(async () => {
        if (name.trim() && name !== node.name) {
            setSaving(true);
            try {
                onRenameNode(node.id, name.trim());
            } finally {
                setSaving(false);
            }
        }
    }, [node.id, node.name, name, onRenameNode]);

    const handleCreateEdge = useCallback(() => {
        if (newEdgeTarget.trim()) {
            onCreateEdge(node.id, newEdgeTarget.trim(), newEdgeRelation);
            setNewEdgeTarget('');
        }
    }, [node.id, newEdgeTarget, newEdgeRelation, onCreateEdge]);

    const masteryPct = Math.round(mastery * 100);

    return (
        <div
            className="absolute right-0 top-0 z-20 h-full w-80 bg-card border-l shadow-lg overflow-y-auto"
            data-testid="node-editor"
        >
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-3">
                <h3 className="font-semibold text-sm">概念详情</h3>
                <button
                    onClick={onClose}
                    className="rounded p-1 hover:bg-accent transition-colors"
                    data-testid="close-editor"
                >
                    <X className="h-4 w-4" />
                </button>
            </div>

            <div className="p-4 space-y-4">
                {/* Concept name */}
                <div>
                    <label className="text-xs text-muted-foreground mb-1 block">名称</label>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="flex-1 rounded border bg-background px-2 py-1.5 text-sm"
                            data-testid="node-name-input"
                        />
                        {name !== node.name && (
                            <button
                                onClick={handleSaveName}
                                disabled={saving}
                                className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                            >
                                <Save className="h-3 w-3" />
                            </button>
                        )}
                    </div>
                </div>

                {/* Type badge */}
                <div>
                    <label className="text-xs text-muted-foreground mb-1 block">类型</label>
                    <span className="inline-block rounded-full bg-muted px-3 py-1 text-xs font-medium">
                        {node.label}
                    </span>
                </div>

                {/* Aliases */}
                {node.aliases.length > 0 && (
                    <div>
                        <label className="text-xs text-muted-foreground mb-1 block">别名</label>
                        <div className="flex flex-wrap gap-1">
                            {node.aliases.map((alias) => (
                                <span
                                    key={alias}
                                    className="rounded bg-muted px-2 py-0.5 text-xs"
                                >
                                    {alias}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Mastery slider */}
                <div>
                    <label className="text-xs text-muted-foreground mb-1 block">
                        掌握度: {masteryPct}%
                    </label>
                    <div className="flex items-center gap-2">
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={mastery}
                            onChange={(e) => setMastery(Number(e.target.value))}
                            className="flex-1"
                            data-testid="mastery-slider"
                        />
                        <button
                            onClick={handleSaveMastery}
                            disabled={saving || mastery === node.mastery}
                            className="rounded bg-primary px-3 py-1 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                            data-testid="save-mastery"
                        >
                            {saving ? '...' : '保存'}
                        </button>
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                        <span>未知</span>
                        <span>了解</span>
                        <span>理解</span>
                        <span>掌握</span>
                    </div>
                </div>

                {/* Connected edges */}
                <div>
                    <label className="text-xs text-muted-foreground mb-1 block">
                        关系 ({connectedEdges.length})
                    </label>
                    {connectedEdges.length === 0 ? (
                        <p className="text-xs text-muted-foreground py-2">暂无关系</p>
                    ) : (
                        <div className="space-y-1 max-h-40 overflow-y-auto">
                            {connectedEdges.map((edge) => {
                                const isSource = edge.source === node.id;
                                const otherNode = isSource ? edge.target : edge.source;
                                return (
                                    <div
                                        key={edge.id}
                                        className="flex items-center justify-between rounded bg-muted/50 px-2 py-1.5 text-xs"
                                    >
                                        <div className="flex items-center gap-1 truncate">
                                            <GitMerge className="h-3 w-3 text-muted-foreground shrink-0" />
                                            <span className="truncate">
                                                {isSource ? `→ ${otherNode}` : `← ${otherNode}`}
                                            </span>
                                            <span className="text-muted-foreground">({edge.label})</span>
                                        </div>
                                        <button
                                            onClick={() => onDeleteEdge(edge.id)}
                                            className="shrink-0 rounded p-0.5 hover:bg-destructive/10 hover:text-destructive transition-colors"
                                            title="删除关系"
                                        >
                                            <Trash2 className="h-3 w-3" />
                                        </button>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Add new edge */}
                <div>
                    <label className="text-xs text-muted-foreground mb-1 block">添加关系</label>
                    <div className="space-y-2">
                        <input
                            type="text"
                            placeholder="目标概念名称..."
                            value={newEdgeTarget}
                            onChange={(e) => setNewEdgeTarget(e.target.value)}
                            className="w-full rounded border bg-background px-2 py-1.5 text-xs"
                            data-testid="new-edge-target"
                        />
                        <div className="flex gap-2">
                            <select
                                value={newEdgeRelation}
                                onChange={(e) => setNewEdgeRelation(e.target.value)}
                                className="flex-1 rounded border bg-background px-2 py-1.5 text-xs"
                                data-testid="new-edge-relation"
                            >
                                {RELATION_TYPES.map((r) => (
                                    <option key={r} value={r}>
                                        {r}
                                    </option>
                                ))}
                            </select>
                            <button
                                onClick={handleCreateEdge}
                                disabled={!newEdgeTarget.trim()}
                                className="rounded bg-primary px-3 py-1 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                                data-testid="add-edge-btn"
                            >
                                添加
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
