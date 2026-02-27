'use client';

import {
    ReactFlow,
    useNodesState,
    useEdgesState,
    useReactFlow,
    ReactFlowProvider,
    Panel,
    type Edge,
    type Node,
    type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useCallback, useEffect, useMemo, useState } from 'react';
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

// Layout algorithms
function applyForceLayout(nodes: Node[]): Node[] {
    // Simple force-directed layout: arrange nodes in a spiral
    const centerX = 400;
    const centerY = 300;
    const nodeCount = nodes.length;

    return nodes.map((node, i) => {
        const angle = (i / nodeCount) * Math.PI * 2 * 3; // 3 rotations
        const radius = 80 + i * 12;
        return {
            ...node,
            position: {
                x: centerX + Math.cos(angle) * radius,
                y: centerY + Math.sin(angle) * radius,
            },
        };
    });
}

function applyHierarchicalLayout(nodes: Node[]): Node[] {
    // Simple hierarchical: sort by mastery, arrange in rows
    const sorted = [...nodes].sort(
        (a, b) => ((b.data as ConceptNodeData).mastery ?? 0) - ((a.data as ConceptNodeData).mastery ?? 0),
    );
    const cols = Math.max(Math.ceil(Math.sqrt(sorted.length)), 3);
    return sorted.map((node, i) => ({
        ...node,
        position: {
            x: (i % cols) * 140 + 50,
            y: Math.floor(i / cols) * 120 + 50,
        },
    }));
}

function applyRadialLayout(nodes: Node[]): Node[] {
    // Radial: concentric circles by mastery
    const centerX = 400;
    const centerY = 350;
    const sorted = [...nodes].sort(
        (a, b) => ((b.data as ConceptNodeData).mastery ?? 0) - ((a.data as ConceptNodeData).mastery ?? 0),
    );

    // Group into 3 rings
    const ringSize = Math.ceil(sorted.length / 3);
    return sorted.map((node, i) => {
        const ring = Math.floor(i / Math.max(ringSize, 1));
        const posInRing = i - ring * ringSize;
        const ringNodes = Math.min(ringSize, sorted.length - ring * ringSize);
        const radius = 100 + ring * 140;
        const angle = (posInRing / ringNodes) * Math.PI * 2 - Math.PI / 2;
        return {
            ...node,
            position: {
                x: centerX + Math.cos(angle) * radius,
                y: centerY + Math.sin(angle) * radius,
            },
        };
    });
}

function applyLayout(nodes: Node[], layout: LayoutType): Node[] {
    switch (layout) {
        case 'hierarchical':
            return applyHierarchicalLayout(nodes);
        case 'radial':
            return applyRadialLayout(nodes);
        case 'force':
        default:
            return applyForceLayout(nodes);
    }
}

// Convert API data to React Flow format
function toFlowNodes(
    kgNodes: KGNodeType[],
    layout: LayoutType,
    heatmapMode: boolean,
    centerConcept: string | null,
    onNodeClick: (nodeId: string) => void,
): Node[] {
    const raw: Node[] = kgNodes.map((n) => ({
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
            heatmapMode,
            onNodeClick,
        } satisfies ConceptNodeData,
    }));
    return applyLayout(raw, layout);
}

function toFlowEdges(kgEdges: KGEdgeType[]): Edge[] {
    return kgEdges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        type: 'smoothstep',
        animated: false,
        style: { stroke: '#94a3b8', strokeWidth: 1.5 },
        labelStyle: { fontSize: 10, fill: '#64748b' },
        labelBgStyle: { fill: 'var(--card)', fillOpacity: 0.8 },
    }));
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

    // Load graph data
    const loadData = useCallback(async () => {
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

        const flowNodes = toFlowNodes(filtered, layout, heatmapMode, centerConcept, handleNodeClick);
        const flowEdges = toFlowEdges(filteredEdges);

        setNodes(flowNodes);
        setEdges(flowEdges);

        // Fit view after layout change
        setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 100);
    }, [graphData, filters, layout, heatmapMode, centerConcept, handleNodeClick, setNodes, setEdges, fitView]);

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
                // Update local state
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

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="animate-pulse text-sm text-muted-foreground">加载知识图谱...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex h-full flex-col items-center justify-center gap-3">
                <p className="text-sm text-destructive">加载失败</p>
                <p className="text-xs text-muted-foreground">{error}</p>
                <button
                    onClick={loadData}
                    className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
                >
                    重试
                </button>
            </div>
        );
    }

    if (!graphData || graphData.nodes.length === 0) {
        return (
            <div className="flex h-full flex-col items-center justify-center gap-2" data-testid="empty-graph">
                <p className="text-sm text-muted-foreground">暂无知识图谱数据</p>
                <p className="text-xs text-muted-foreground">开始阅读内容并给出反馈，系统会自动构建您的知识图谱</p>
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
                fitViewOptions={{ padding: 0.2 }}
                minZoom={0.1}
                maxZoom={3}
                proOptions={{ hideAttribution: true }}
            >
                {/* Controls overlay */}
                <GraphControls
                    communities={communities}
                    filters={filters}
                    onFiltersChange={setFilters}
                    layout={layout}
                    onLayoutChange={setLayout}
                    heatmapMode={heatmapMode}
                    onHeatmapToggle={() => setHeatmapMode((prev) => !prev)}
                    onFitView={() => fitView({ padding: 0.2, duration: 300 })}
                    onSearch={handleSearch}
                />

                {/* Stats panel */}
                <Panel position="top-right">
                    <div className="rounded-lg bg-card border shadow-sm px-3 py-2 text-xs text-muted-foreground">
                        <span>{graphData.total_nodes} 个概念</span>
                        <span className="mx-1.5">·</span>
                        <span>{graphData.total_edges} 个关系</span>
                        {centerConcept && (
                            <>
                                <span className="mx-1.5">·</span>
                                <button
                                    onClick={() => setCenterConcept(null)}
                                    className="text-primary hover:underline"
                                >
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
