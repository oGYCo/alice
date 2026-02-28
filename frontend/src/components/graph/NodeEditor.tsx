'use client';

import { useState, useCallback, useMemo } from 'react';
import { X, Save, Trash2, GitMerge, Plus, ArrowRight, ArrowLeft } from 'lucide-react';
import type { KGNode, KGEdge } from '@/lib/types';

interface NodeEditorProps {
    node: KGNode;
    edges: KGEdge[];
    allNodes: KGNode[];
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

const RELATION_LABELS_ZH: Record<string, string> = {
    PREREQUISITE_OF: '前置知识',
    EXTENDS: '扩展',
    APPLIES_TO: '应用于',
    CONTRASTS: '对比',
};

const TYPE_THEME: Record<string, { bg: string; text: string; icon: string }> = {
    Concept: { bg: 'bg-sky-100 dark:bg-sky-900/40', text: 'text-sky-700 dark:text-sky-300', icon: '💡' },
    Method: { bg: 'bg-pink-100 dark:bg-pink-900/40', text: 'text-pink-700 dark:text-pink-300', icon: '⚙️' },
    Tool: { bg: 'bg-emerald-100 dark:bg-emerald-900/40', text: 'text-emerald-700 dark:text-emerald-300', icon: '🔧' },
    Theory: { bg: 'bg-amber-100 dark:bg-amber-900/40', text: 'text-amber-700 dark:text-amber-300', icon: '📐' },
};

function getMasteryLabel(mastery: number): { label: string; color: string } {
    if (mastery >= 0.8) return { label: '已掌握', color: 'text-green-600 dark:text-green-400' };
    if (mastery >= 0.5) return { label: '理解中', color: 'text-yellow-600 dark:text-yellow-400' };
    if (mastery >= 0.3) return { label: '了解', color: 'text-orange-600 dark:text-orange-400' };
    return { label: '未知', color: 'text-red-500 dark:text-red-400' };
}

function getMasteryBarColor(mastery: number): string {
    if (mastery >= 0.8) return 'bg-green-500';
    if (mastery >= 0.5) return 'bg-yellow-500';
    if (mastery >= 0.3) return 'bg-orange-500';
    return 'bg-red-400';
}

export function NodeEditor({
    node,
    edges,
    allNodes,
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
    const [showSuggestions, setShowSuggestions] = useState(false);

    // Edges connected to this node
    const connectedEdges = edges.filter(
        (e) => e.source === node.id || e.target === node.id,
    );

    // Autocomplete suggestions
    const suggestions = useMemo(() => {
        if (!newEdgeTarget.trim()) return [];
        const query = newEdgeTarget.toLowerCase();
        const connectedIds = new Set(connectedEdges.map((e) => e.source === node.id ? e.target : e.source));
        return allNodes
            .filter((n) =>
                n.id !== node.id &&
                !connectedIds.has(n.id) &&
                (n.name.toLowerCase().includes(query) || n.aliases.some((a) => a.toLowerCase().includes(query)))
            )
            .slice(0, 5);
    }, [newEdgeTarget, allNodes, node.id, connectedEdges]);

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
            setShowSuggestions(false);
        }
    }, [node.id, newEdgeTarget, newEdgeRelation, onCreateEdge]);

    const masteryPct = Math.round(mastery * 100);
    const masteryInfo = getMasteryLabel(mastery);
    const typeTheme = TYPE_THEME[node.label] ?? TYPE_THEME.Concept;

    return (
        <div
            className="absolute right-0 top-0 z-20 h-full w-80 bg-card/95 backdrop-blur-md
                       border-l border-border/50 shadow-2xl overflow-y-auto
                       animate-in slide-in-from-right-4 duration-300"
            data-testid="node-editor"
        >
            {/* Header with concept highlight */}
            <div className="sticky top-0 bg-card/95 backdrop-blur-md border-b border-border/30 z-10">
                <div className="flex items-start justify-between px-4 pt-4 pb-3">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                            <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${typeTheme.bg} ${typeTheme.text}`}>
                                {typeTheme.icon} {node.label}
                            </span>
                        </div>
                        <h3 className="font-semibold text-base truncate" title={node.name}>
                            {node.name}
                        </h3>
                    </div>
                    <button
                        onClick={onClose}
                        className="rounded-lg p-1.5 hover:bg-accent transition-colors mt-0.5 shrink-0"
                        data-testid="close-editor"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>
            </div>

            <div className="p-4 space-y-5">
                {/* Mastery section — visual bar */}
                <div>
                    <div className="flex items-center justify-between mb-2">
                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">掌握度</label>
                        <span className={`text-xs font-semibold ${masteryInfo.color}`}>
                            {masteryPct}% · {masteryInfo.label}
                        </span>
                    </div>
                    {/* Visual progress bar */}
                    <div className="h-2 w-full rounded-full bg-muted/50 mb-3 overflow-hidden">
                        <div
                            className={`h-full rounded-full transition-all duration-500 ${getMasteryBarColor(mastery)}`}
                            style={{ width: `${masteryPct}%` }}
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={mastery}
                            onChange={(e) => setMastery(Number(e.target.value))}
                            className="flex-1 accent-primary"
                            data-testid="mastery-slider"
                        />
                        <button
                            onClick={handleSaveMastery}
                            disabled={saving || mastery === node.mastery}
                            className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground
                                       hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed
                                       transition-all duration-200 shadow-sm"
                            data-testid="save-mastery"
                        >
                            {saving ? '...' : '保存'}
                        </button>
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground/70 mt-1 px-0.5">
                        <span>未知</span>
                        <span>了解</span>
                        <span>理解</span>
                        <span>掌握</span>
                    </div>
                </div>

                {/* Rename section */}
                <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1.5 block uppercase tracking-wider">名称</label>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="flex-1 rounded-lg border border-border/50 bg-background/80 px-3 py-2 text-sm
                                       focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50 transition-all"
                            data-testid="node-name-input"
                        />
                        {name !== node.name && (
                            <button
                                onClick={handleSaveName}
                                disabled={saving}
                                className="rounded-lg bg-primary px-3 py-2 text-primary-foreground hover:bg-primary/90
                                           disabled:opacity-50 transition-colors shadow-sm"
                            >
                                <Save className="h-3.5 w-3.5" />
                            </button>
                        )}
                    </div>
                </div>

                {/* Aliases */}
                {node.aliases.length > 0 && (
                    <div>
                        <label className="text-xs font-medium text-muted-foreground mb-1.5 block uppercase tracking-wider">别名</label>
                        <div className="flex flex-wrap gap-1.5">
                            {node.aliases.map((alias) => (
                                <span
                                    key={alias}
                                    className="rounded-lg bg-muted/50 px-2.5 py-1 text-xs font-medium text-muted-foreground"
                                >
                                    {alias}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Connected edges — styled list */}
                <div>
                    <label className="text-xs font-medium text-muted-foreground mb-2 block uppercase tracking-wider">
                        关系 <span className="text-foreground/60">({connectedEdges.length})</span>
                    </label>
                    {connectedEdges.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-border/50 py-4 text-center">
                            <p className="text-xs text-muted-foreground/60">暂无关系</p>
                        </div>
                    ) : (
                        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                            {connectedEdges.map((edge) => {
                                const isSource = edge.source === node.id;
                                const otherNode = isSource ? edge.target : edge.source;
                                const zhLabel = RELATION_LABELS_ZH[edge.label] ?? edge.label;
                                return (
                                    <div
                                        key={edge.id}
                                        className="flex items-center justify-between rounded-lg bg-muted/30
                                                   hover:bg-muted/50 px-3 py-2 text-xs group/edge transition-colors"
                                    >
                                        <div className="flex items-center gap-2 truncate min-w-0">
                                            {isSource ? (
                                                <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                                            ) : (
                                                <ArrowLeft className="h-3 w-3 text-muted-foreground shrink-0" />
                                            )}
                                            <span className="font-medium truncate">{otherNode}</span>
                                            <span className="text-muted-foreground/60 shrink-0 text-[10px]">{zhLabel}</span>
                                        </div>
                                        <button
                                            onClick={() => onDeleteEdge(edge.id)}
                                            className="shrink-0 rounded-md p-1 opacity-0 group-hover/edge:opacity-100
                                                       hover:bg-destructive/10 hover:text-destructive transition-all"
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

                {/* Add new edge — with autocomplete */}
                <div>
                    <label className="text-xs font-medium text-muted-foreground mb-2 block uppercase tracking-wider">
                        <Plus className="h-3 w-3 inline mr-1" />
                        添加关系
                    </label>
                    <div className="space-y-2">
                        <div className="relative">
                            <input
                                type="text"
                                placeholder="目标概念名称..."
                                value={newEdgeTarget}
                                onChange={(e) => {
                                    setNewEdgeTarget(e.target.value);
                                    setShowSuggestions(true);
                                }}
                                onFocus={() => setShowSuggestions(true)}
                                onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                                className="w-full rounded-lg border border-border/50 bg-background/80 px-3 py-2 text-xs
                                           focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50 transition-all"
                                data-testid="new-edge-target"
                            />
                            {/* Autocomplete dropdown */}
                            {showSuggestions && suggestions.length > 0 && (
                                <div className="absolute top-full left-0 right-0 mt-1 rounded-lg bg-popover border border-border/50
                                                shadow-lg overflow-hidden z-30 animate-in fade-in slide-in-from-top-1 duration-150">
                                    {suggestions.map((s) => (
                                        <button
                                            key={s.id}
                                            onMouseDown={(e) => e.preventDefault()}
                                            onClick={() => {
                                                setNewEdgeTarget(s.name);
                                                setShowSuggestions(false);
                                            }}
                                            className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-accent transition-colors text-left"
                                        >
                                            <span className="font-medium">{s.name}</span>
                                            <span className="text-muted-foreground/60 text-[10px]">{s.label}</span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                        <div className="flex gap-2">
                            <select
                                value={newEdgeRelation}
                                onChange={(e) => setNewEdgeRelation(e.target.value)}
                                className="flex-1 rounded-lg border border-border/50 bg-background/80 px-2.5 py-2 text-xs
                                           focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50 transition-all"
                                data-testid="new-edge-relation"
                            >
                                {RELATION_TYPES.map((r) => (
                                    <option key={r} value={r}>
                                        {RELATION_LABELS_ZH[r] ?? r}
                                    </option>
                                ))}
                            </select>
                            <button
                                onClick={handleCreateEdge}
                                disabled={!newEdgeTarget.trim()}
                                className="rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground
                                           hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed
                                           transition-all duration-200 shadow-sm"
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
