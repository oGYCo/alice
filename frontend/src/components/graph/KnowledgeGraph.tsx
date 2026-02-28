'use client';

import {
    ReactFlow,
    useNodesState,
    useEdgesState,
    useReactFlow,
    ReactFlowProvider,
    Panel,
    Background,
    BackgroundVariant,
    MiniMap,
    Controls,
    type Edge,
    type Node,
    type NodeTypes,
    MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { apiClient } from '@/lib/api';
import type { KGGraph, KGCommunity, KGGapAnalysis, KGNode as KGNodeType, KGEdge as KGEdgeType } from '@/lib/types';
import ConceptNodeComponent, { type ConceptNodeData } from './ConceptNode';
import { GraphControls, type GraphFilters, type LayoutType } from './GraphControls';
import { NodeEditor } from './NodeEditor';
import { GapAnalysisPanel } from './GapAnalysisPanel';

// Register custom node types
const nodeTypes: NodeTypes = {
    concept: ConceptNodeComponent,
};

// ── Edge color palette by relationship type ───────────────────────────────────
const EDGE_COLORS: Record<string, string> = {
    PREREQUISITE_OF: '#6366f1', // indigo
    EXTENDS: '#0ea5e9',         // sky
    APPLIES_TO: '#10b981',      // emerald
    CONTRASTS: '#f43f5e',       // rose
};
const EDGE_DEFAULT_COLOR = '#94a3b8';

const EDGE_LABELS_ZH: Record<string, string> = {
    PREREQUISITE_OF: '前置',
    EXTENDS: '扩展',
    APPLIES_TO: '应用于',
    CONTRASTS: '对比',
};

// ── Layout Algorithms ─────────────────────────────────────────────────────────

function applyForceLayout(nodes: Node[], edges: Edge[]): Node[] {
    // Improved force‑directed layout with repulsion + spring edges
    if (nodes.length === 0) return nodes;

    const positions = new Map<string, { x: number; y: number }>();
    const centerX = 500;
    const centerY = 400;

    // Initialize in a circle
    nodes.forEach((node, i) => {
        const angle = (i / nodes.length) * Math.PI * 2;
        const radius = 160 + Math.sqrt(nodes.length) * 30;
        positions.set(node.id, {
            x: centerX + Math.cos(angle) * radius,
            y: centerY + Math.sin(angle) * radius,
        });
    });

    // Build adjacency
    const adj = new Map<string, Set<string>>();
    for (const e of edges) {
        if (!adj.has(e.source)) adj.set(e.source, new Set());
        if (!adj.has(e.target)) adj.set(e.target, new Set());
        adj.get(e.source)!.add(e.target);
        adj.get(e.target)!.add(e.source);
    }

    // Simple iterative force simulation (20 iterations)
    const k = 120; // ideal spring length
    for (let iter = 0; iter < 25; iter++) {
        const cooling = 1 - iter / 30;
        const disp = new Map<string, { dx: number; dy: number }>();
        for (const n of nodes) disp.set(n.id, { dx: 0, dy: 0 });

        // Repulsion between all pairs
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const pi = positions.get(nodes[i].id)!;
                const pj = positions.get(nodes[j].id)!;
                const dx = pi.x - pj.x;
                const dy = pi.y - pj.y;
                const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
                const force = (k * k) / dist;
                const fx = (dx / dist) * force * cooling;
                const fy = (dy / dist) * force * cooling;
                disp.get(nodes[i].id)!.dx += fx;
                disp.get(nodes[i].id)!.dy += fy;
                disp.get(nodes[j].id)!.dx -= fx;
                disp.get(nodes[j].id)!.dy -= fy;
            }
        }

        // Attraction along edges
        for (const e of edges) {
            const ps = positions.get(e.source);
            const pt = positions.get(e.target);
            if (!ps || !pt) continue;
            const dx = ps.x - pt.x;
            const dy = ps.y - pt.y;
            const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
            const force = dist / k;
            const fx = (dx / dist) * force * cooling * 0.5;
            const fy = (dy / dist) * force * cooling * 0.5;
            if (disp.has(e.source)) { disp.get(e.source)!.dx -= fx; disp.get(e.source)!.dy -= fy; }
            if (disp.has(e.target)) { disp.get(e.target)!.dx += fx; disp.get(e.target)!.dy += fy; }
        }

        // Apply displacements
        for (const n of nodes) {
            const d = disp.get(n.id)!;
            const p = positions.get(n.id)!;
            const mag = Math.sqrt(d.dx * d.dx + d.dy * d.dy);
            const maxDisp = 40 * cooling;
            if (mag > maxDisp) {
                d.dx = (d.dx / mag) * maxDisp;
                d.dy = (d.dy / mag) * maxDisp;
            }
            p.x += d.dx;
            p.y += d.dy;
        }
    }

    return nodes.map((node) => ({
        ...node,
        position: positions.get(node.id) ?? { x: 0, y: 0 },
    }));
}

function applyHierarchicalLayout(nodes: Node[]): Node[] {
    const sorted = [...nodes].sort(
        (a, b) => ((b.data as ConceptNodeData).mastery ?? 0) - ((a.data as ConceptNodeData).mastery ?? 0),
    );
    const cols = Math.max(Math.ceil(Math.sqrt(sorted.length * 1.5)), 3);
    return sorted.map((node, i) => ({
        ...node,
        position: {
            x: (i % cols) * 160 + 60,
            y: Math.floor(i / cols) * 140 + 60,
        },
    }));
}

function applyRadialLayout(nodes: Node[]): Node[] {
    const centerX = 500;
    const centerY = 450;
    const sorted = [...nodes].sort(
        (a, b) => ((b.data as ConceptNodeData).mastery ?? 0) - ((a.data as ConceptNodeData).mastery ?? 0),
    );

    if (sorted.length <= 1) {
        return sorted.map((n) => ({ ...n, position: { x: centerX, y: centerY } }));
    }

    // Place top-mastery node at center, rest in concentric rings
    const result = [{ ...sorted[0], position: { x: centerX, y: centerY } }];
    const rest = sorted.slice(1);
    const ringCapacities = [6, 12, 18, 24, 36]; // nodes per ring
    let idx = 0;

    for (let ring = 0; ring < ringCapacities.length && idx < rest.length; ring++) {
        const capacity = ringCapacities[ring];
        const nodesInRing = Math.min(capacity, rest.length - idx);
        const radius = 120 + ring * 110;
        for (let j = 0; j < nodesInRing; j++) {
            const angle = (j / nodesInRing) * Math.PI * 2 - Math.PI / 2;
            result.push({
                ...rest[idx],
                position: {
                    x: centerX + Math.cos(angle) * radius,
                    y: centerY + Math.sin(angle) * radius,
                },
            });
            idx++;
        }
    }

    // Overflow nodes in outer ring
    if (idx < rest.length) {
        const remaining = rest.length - idx;
        const radius = 120 + ringCapacities.length * 110;
        for (let j = 0; idx < rest.length; j++, idx++) {
            const angle = (j / remaining) * Math.PI * 2 - Math.PI / 2;
            result.push({
                ...rest[idx],
                position: {
                    x: centerX + Math.cos(angle) * radius,
                    y: centerY + Math.sin(angle) * radius,
                },
            });
        }
    }

    return result;
}

function applyLayout(nodes: Node[], layout: LayoutType, edges: Edge[]): Node[] {
    switch (layout) {
        case 'hierarchical':
            return applyHierarchicalLayout(nodes);
        case 'radial':
            return applyRadialLayout(nodes);
        case 'force':
        default:
            return applyForceLayout(nodes, edges);
    }
}

// ── Data Conversion ───────────────────────────────────────────────────────────

function toFlowNodes(
    kgNodes: KGNodeType[],
    heatmapMode: boolean,
    centerConcept: string | null,
    selectedNodeId: string | null,
    onNodeClick: (nodeId: string) => void,
): Node[] {
    return kgNodes.map((n) => ({
        id: n.id,
        type: 'concept',
        position: { x: 0, y: 0 },
        data: {
            name: n.name,
            label: n.label,
            mastery: n.mastery,
            communityId: n.community_id,
            aliases: n.aliases,
            isCenter: n.id === centerConcept,
            selected: n.id === selectedNodeId,
            heatmapMode,
            onNodeClick,
        } satisfies ConceptNodeData,
    }));
}

function toFlowEdges(kgEdges: KGEdgeType[]): Edge[] {
    return kgEdges.map((e) => {
        const color = EDGE_COLORS[e.label] ?? EDGE_DEFAULT_COLOR;
        const zhLabel = EDGE_LABELS_ZH[e.label] ?? e.label;
        return {
            id: e.id,
            source: e.source,
            target: e.target,
            label: zhLabel,
            type: 'default',
            animated: e.label === 'PREREQUISITE_OF',
            style: {
                stroke: color,
                strokeWidth: e.label === 'PREREQUISITE_OF' ? 2 : 1.5,
                opacity: 0.7,
            },
            labelStyle: {
                fontSize: 10,
                fontWeight: 500,
                fill: color,
                letterSpacing: '0.02em',
            },
            labelBgStyle: {
                fill: 'var(--card)',
                fillOpacity: 0.9,
                rx: 4,
                ry: 4,
            },
            labelBgPadding: [4, 6] as [number, number],
            markerEnd: {
                type: MarkerType.ArrowClosed,
                width: 14,
                height: 14,
                color,
            },
        };
    });
}

function filterNodes(
    nodes: KGNodeType[],
    filters: GraphFilters,
): KGNodeType[] {
    return nodes.filter((n) => {
        if (filters.communityId !== null && n.community_id !== filters.communityId) return false;
        if (filters.conceptType && n.label !== filters.conceptType) return false;
        if (n.mastery < filters.masteryRange[0] || n.mastery > filters.masteryRange[1]) return false;
        if (
            filters.searchQuery &&
            !n.name.toLowerCase().includes(filters.searchQuery.toLowerCase()) &&
            !n.aliases.some((a) => a.toLowerCase().includes(filters.searchQuery.toLowerCase()))
        ) {
            return false;
        }
        return true;
    });
}

// ── MiniMap node color helper ─────────────────────────────────────────────────
function miniMapNodeColor(node: Node): string {
    const data = node.data as ConceptNodeData;
    if (data.mastery >= 0.8) return '#22c55e';
    if (data.mastery >= 0.5) return '#eab308';
    if (data.mastery >= 0.3) return '#f97316';
    return '#ef4444';
}

// ── Main Component ────────────────────────────────────────────────────────────

interface KnowledgeGraphInnerProps {
    userId?: number;
}

function KnowledgeGraphInner({ userId = 1 }: KnowledgeGraphInnerProps) {
    const { fitView } = useReactFlow();

    // Data state
    const [graphData, setGraphData] = useState<KGGraph | null>(null);
    const [communities, setCommunities] = useState<KGCommunity[]>([]);
    const [gapAnalysis, setGapAnalysis] = useState<KGGapAnalysis | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // UI state
    const [layout, setLayout] = useState<LayoutType>('force');
    const [heatmapMode, setHeatmapMode] = useState(false);
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
    const [centerConcept, setCenterConcept] = useState<string | null>(null);
    const [filters, setFilters] = useState<GraphFilters>({
        communityId: null,
        masteryRange: [0, 1],
        conceptType: null,
        searchQuery: '',
    });

    // React Flow state
    const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[]);

    // Prevent duplicate load
    const loadingRef = useRef(false);

    // Load graph data
    const loadData = useCallback(async () => {
        if (loadingRef.current) return;
        loadingRef.current = true;
        setLoading(true);
        setError(null);
        try {
            const [graph, comms, gaps] = await Promise.all([
                apiClient.getKGGraph({ userId, center: centerConcept ?? undefined }),
                apiClient.getKGCommunities(userId),
                apiClient.getKGGaps(userId),
            ]);
            setGraphData(graph);
            setCommunities(comms);
            setGapAnalysis(gaps);
        } catch (err) {
            const msg = err instanceof Error ? err.message : '加载知识图谱失败';
            setError(msg);
        } finally {
            setLoading(false);
            loadingRef.current = false;
        }
    }, [userId, centerConcept]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    // Handle node click — open editor sidebar
    const handleNodeClick = useCallback((nodeId: string) => {
        setSelectedNodeId((prev) => (prev === nodeId ? null : nodeId));
    }, []);

    // Update nodes/edges when data or filters change
    useEffect(() => {
        if (!graphData) return;

        const filtered = filterNodes(graphData.nodes, filters);
        const filteredIds = new Set(filtered.map((n) => n.id));
        const filteredEdges = graphData.edges.filter(
            (e) => filteredIds.has(e.source) && filteredIds.has(e.target),
        );

        const rawNodes = toFlowNodes(filtered, heatmapMode, centerConcept, selectedNodeId, handleNodeClick);
        const flowEdges = toFlowEdges(filteredEdges);
        const flowNodes = applyLayout(rawNodes, layout, flowEdges);

        setNodes(flowNodes);
        setEdges(flowEdges);

        // Fit view after layout change
        setTimeout(() => fitView({ padding: 0.15, duration: 400 }), 120);
    }, [graphData, filters, layout, heatmapMode, centerConcept, selectedNodeId, handleNodeClick, setNodes, setEdges, fitView]);

    // Handle search — center on found concept
    const handleSearch = useCallback(
        (query: string) => {
            if (!query || !graphData) return;
            const match = graphData.nodes.find(
                (n) =>
                    n.name.toLowerCase() === query.toLowerCase() ||
                    n.aliases.some((a) => a.toLowerCase() === query.toLowerCase()),
            );
            if (match) {
                setSelectedNodeId(match.id);
            }
        },
        [graphData],
    );

    // Handler: navigate to concept
    const handleConceptClick = useCallback((concept: string) => {
        setCenterConcept(concept);
    }, []);

    // Handler: update mastery
    const handleUpdateMastery = useCallback(
        async (nodeId: string, mastery: number) => {
            try {
                await apiClient.updateKGNode(nodeId, { mastery }, userId);
                setGraphData((prev) => {
                    if (!prev) return prev;
                    return {
                        ...prev,
                        nodes: prev.nodes.map((n) =>
                            n.id === nodeId ? { ...n, mastery } : n,
                        ),
                    };
                });
            } catch (err) {
                console.error('Failed to update mastery:', err);
            }
        },
        [userId],
    );

    // Handler: rename node
    const handleRenameNode = useCallback(
        async (nodeId: string, newName: string) => {
            try {
                await apiClient.updateKGNode(nodeId, { name: newName }, userId);
                setGraphData((prev) => {
                    if (!prev) return prev;
                    return {
                        ...prev,
                        nodes: prev.nodes.map((n) =>
                            n.id === nodeId ? { ...n, id: newName, name: newName } : n,
                        ),
                    };
                });
                setSelectedNodeId(newName);
            } catch (err) {
                console.error('Failed to rename node:', err);
            }
        },
        [userId],
    );

    // Handler: create edge
    const handleCreateEdge = useCallback(
        async (source: string, target: string, relation: string) => {
            try {
                const result = await apiClient.createKGEdge(source, target, relation, userId);
                setGraphData((prev) => {
                    if (!prev) return prev;
                    return {
                        ...prev,
                        edges: [
                            ...prev.edges,
                            { id: result.id, source, target, label: relation },
                        ],
                    };
                });
            } catch (err) {
                console.error('Failed to create edge:', err);
            }
        },
        [userId],
    );

    // Handler: delete edge
    const handleDeleteEdge = useCallback(
        async (edgeId: string) => {
            try {
                await apiClient.deleteKGEdge(edgeId, userId);
                setGraphData((prev) => {
                    if (!prev) return prev;
                    return {
                        ...prev,
                        edges: prev.edges.filter((e) => e.id !== edgeId),
                    };
                });
            } catch (err) {
                console.error('Failed to delete edge:', err);
            }
        },
        [userId],
    );

    // Find selected node data
    const selectedNode = useMemo(
        () => graphData?.nodes.find((n) => n.id === selectedNodeId) ?? null,
        [graphData, selectedNodeId],
    );

    // Compute stats
    const stats = useMemo(() => {
        if (!graphData || graphData.nodes.length === 0) return null;
        const avgMastery = graphData.nodes.reduce((s, n) => s + n.mastery, 0) / graphData.nodes.length;
        const mastered = graphData.nodes.filter((n) => n.mastery >= 0.8).length;
        const learning = graphData.nodes.filter((n) => n.mastery >= 0.3 && n.mastery < 0.8).length;
        const unknown = graphData.nodes.filter((n) => n.mastery < 0.3).length;
        return { avgMastery, mastered, learning, unknown };
    }, [graphData]);

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center bg-gradient-to-br from-muted/30 to-background">
                <div className="flex flex-col items-center gap-4">
                    <div className="relative h-12 w-12">
                        <div className="absolute inset-0 rounded-full border-2 border-muted" />
                        <div className="absolute inset-0 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                    </div>
                    <p className="text-sm text-muted-foreground animate-pulse">加载知识图谱...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex h-full flex-col items-center justify-center gap-4 bg-gradient-to-br from-muted/30 to-background">
                <div className="rounded-full bg-destructive/10 p-4">
                    <svg className="h-8 w-8 text-destructive" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                    </svg>
                </div>
                <div className="text-center">
                    <p className="text-sm font-medium text-destructive">知识图谱加载失败</p>
                    <p className="text-xs text-muted-foreground mt-1 max-w-xs">{error}</p>
                </div>
                <button
                    onClick={loadData}
                    className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground
                               hover:bg-primary/90 transition-colors shadow-sm"
                >
                    重试
                </button>
            </div>
        );
    }

    if (!graphData || graphData.nodes.length === 0) {
        return (
            <div className="flex h-full flex-col items-center justify-center gap-5 bg-gradient-to-br from-muted/30 to-background" data-testid="empty-graph">
                <div className="rounded-full bg-muted/50 p-6">
                    <svg className="h-12 w-12 text-muted-foreground/50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
                    </svg>
                </div>
                <div className="text-center">
                    <p className="text-base font-medium text-foreground">尚无知识图谱</p>
                    <p className="text-sm text-muted-foreground mt-1.5 max-w-sm leading-relaxed">
                        开始阅读内容并给出反馈，<br/>系统将自动构建您的个人知识图谱
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="relative h-full w-full" data-testid="knowledge-graph">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.15 }}
                minZoom={0.05}
                maxZoom={4}
                proOptions={{ hideAttribution: true }}
                className="!bg-gradient-to-br from-background via-background to-muted/20"
                defaultEdgeOptions={{
                    type: 'default',
                    style: { strokeWidth: 1.5 },
                }}
            >
                <Background
                    variant={BackgroundVariant.Dots}
                    gap={20}
                    size={1}
                    color="var(--color-muted-foreground)"
                    className="opacity-20"
                />

                <MiniMap
                    nodeColor={miniMapNodeColor}
                    maskColor="rgba(0,0,0,0.08)"
                    className="!bg-card/80 !backdrop-blur-sm !border !border-border/50 !rounded-lg !shadow-lg"
                    style={{ width: 160, height: 100 }}
                    pannable
                    zoomable
                />

                <Controls
                    showInteractive={false}
                    className="!bg-card !border !border-border/50 !rounded-lg !shadow-md [&>button]:!bg-card [&>button]:!border-border/30 [&>button]:hover:!bg-accent [&>button]:!rounded [&>button]:!text-foreground"
                />

                {/* Controls overlay */}
                <GraphControls
                    communities={communities}
                    filters={filters}
                    onFiltersChange={setFilters}
                    layout={layout}
                    onLayoutChange={setLayout}
                    heatmapMode={heatmapMode}
                    onHeatmapToggle={() => setHeatmapMode((prev) => !prev)}
                    onFitView={() => fitView({ padding: 0.15, duration: 400 })}
                    onSearch={handleSearch}
                />

                {/* Top-right stats panel */}
                <Panel position="top-right">
                    <div className="flex items-center gap-3 rounded-xl bg-card/90 backdrop-blur-sm border border-border/50 shadow-lg px-4 py-2.5">
                        <div className="flex items-center gap-2">
                            <div className="flex items-center gap-1.5">
                                <div className="h-2 w-2 rounded-full bg-foreground/60" />
                                <span className="text-xs font-medium text-foreground">{graphData.total_nodes}</span>
                                <span className="text-xs text-muted-foreground">概念</span>
                            </div>
                            <div className="h-3 w-px bg-border" />
                            <div className="flex items-center gap-1.5">
                                <div className="h-2 w-2 rounded-full bg-muted-foreground/40" />
                                <span className="text-xs font-medium text-foreground">{graphData.total_edges}</span>
                                <span className="text-xs text-muted-foreground">关系</span>
                            </div>
                        </div>

                        {stats && (
                            <>
                                <div className="h-3 w-px bg-border" />
                                <div className="flex items-center gap-2">
                                    <span className="flex items-center gap-1 text-[11px]">
                                        <span className="h-2 w-2 rounded-full bg-green-500" />
                                        <span className="text-muted-foreground">{stats.mastered}</span>
                                    </span>
                                    <span className="flex items-center gap-1 text-[11px]">
                                        <span className="h-2 w-2 rounded-full bg-yellow-500" />
                                        <span className="text-muted-foreground">{stats.learning}</span>
                                    </span>
                                    <span className="flex items-center gap-1 text-[11px]">
                                        <span className="h-2 w-2 rounded-full bg-red-400" />
                                        <span className="text-muted-foreground">{stats.unknown}</span>
                                    </span>
                                </div>
                            </>
                        )}

                        {centerConcept && (
                            <>
                                <div className="h-3 w-px bg-border" />
                                <button
                                    onClick={() => setCenterConcept(null)}
                                    className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors font-medium"
                                >
                                    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
                                    </svg>
                                    返回全图
                                </button>
                            </>
                        )}
                    </div>
                </Panel>

                {/* Gap analysis panel */}
                <Panel position="bottom-left">
                    <GapAnalysisPanel
                        gaps={gapAnalysis?.gaps ?? []}
                        totalGaps={gapAnalysis?.total_gaps ?? 0}
                        onConceptClick={handleConceptClick}
                    />
                </Panel>
            </ReactFlow>

            {/* Node editor sidebar */}
            {selectedNode && (
                <NodeEditor
                    node={selectedNode}
                    edges={graphData.edges}
                    allNodes={graphData.nodes}
                    onClose={() => setSelectedNodeId(null)}
                    onUpdateMastery={handleUpdateMastery}
                    onRenameNode={handleRenameNode}
                    onDeleteEdge={handleDeleteEdge}
                    onCreateEdge={handleCreateEdge}
                />
            )}
        </div>
    );
}

export interface KnowledgeGraphProps {
    userId?: number;
}

export function KnowledgeGraph({ userId }: KnowledgeGraphProps) {
    return (
        <ReactFlowProvider>
            <KnowledgeGraphInner userId={userId} />
        </ReactFlowProvider>
    );
}
