import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { KnowledgeGraph } from '../KnowledgeGraph';
import type { KGGraph, KGCommunity, KGGapAnalysis } from '@/lib/types';

// Mock @xyflow/react
vi.mock('@xyflow/react', () => {
    const ReactFlowProvider = ({ children }: { children: React.ReactNode }) => <div>{children}</div>;
    const Panel = ({ children, position }: { children: React.ReactNode; position: string }) => (
        <div data-testid={`panel-${position}`}>{children}</div>
    );
    const ReactFlow = ({ children, nodes, edges }: { children?: React.ReactNode; nodes: unknown[]; edges: unknown[] }) => (
        <div data-testid="react-flow" data-nodes={nodes.length} data-edges={edges.length}>
            {children}
        </div>
    );

    return {
        ReactFlow,
        ReactFlowProvider,
        Panel,
        Handle: () => null,
        Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
        Background: () => null,
        BackgroundVariant: { Dots: 'dots', Lines: 'lines', Cross: 'cross' },
        MarkerType: { Arrow: 'arrow', ArrowClosed: 'arrowclosed' },
        MiniMap: () => null,
        Controls: () => null,
        useNodesState: (initial: unknown[]) => {
            const { useState } = require('react');
            const [nodes, setNodes] = useState(initial);
            return [nodes, setNodes, vi.fn()];
        },
        useEdgesState: (initial: unknown[]) => {
            const { useState } = require('react');
            const [edges, setEdges] = useState(initial);
            return [edges, setEdges, vi.fn()];
        },
        useReactFlow: () => ({
            fitView: vi.fn(),
            setCenter: vi.fn(),
            getZoom: vi.fn(() => 1),
        }),
    };
});

// Mock next/link
vi.mock('next/link', () => ({
    default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
        <a href={href} {...props}>{children}</a>
    ),
}));

const mockGraphData: KGGraph = {
    nodes: [
        { id: 'Attention Mechanism', name: 'Attention Mechanism', label: 'Concept', mastery: 0.85, community_id: 0, aliases: ['attention'] },
        { id: 'Transformer', name: 'Transformer', label: 'Method', mastery: 0.7, community_id: 0, aliases: [] },
        { id: 'PyTorch', name: 'PyTorch', label: 'Tool', mastery: 0.6, community_id: 1, aliases: [] },
        { id: 'Information Theory', name: 'Information Theory', label: 'Theory', mastery: 0.3, community_id: 1, aliases: [] },
    ],
    edges: [
        { id: 'Attention Mechanism-PREREQUISITE_OF-Transformer', source: 'Attention Mechanism', target: 'Transformer', label: 'PREREQUISITE_OF' },
        { id: 'Transformer-APPLIES_TO-PyTorch', source: 'Transformer', target: 'PyTorch', label: 'APPLIES_TO' },
    ],
    total_nodes: 4,
    total_edges: 2,
};

const mockCommunities: KGCommunity[] = [
    { community_id: 0, label: 'Deep Learning', concept_count: 10, avg_mastery: 0.75, concepts: ['Attention Mechanism', 'Transformer'] },
    { community_id: 1, label: 'Systems', concept_count: 5, avg_mastery: 0.45, concepts: ['PyTorch'] },
];

const mockGaps: KGGapAnalysis = {
    gaps: [
        { concept: 'Ring Attention', mastery: 0.1, adjacent_mastered: ['Attention Mechanism'], reason: '与已掌握概念 Attention Mechanism 相邻' },
    ],
    total_gaps: 1,
};

// Use vi.hoisted to ensure mock fns are available before vi.mock hoisting
const { getKGGraph, getKGCommunities, getKGGaps, updateKGNode, createKGEdge, deleteKGEdge } = vi.hoisted(() => ({
    getKGGraph: vi.fn(),
    getKGCommunities: vi.fn(),
    getKGGaps: vi.fn(),
    updateKGNode: vi.fn(),
    createKGEdge: vi.fn(),
    deleteKGEdge: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
    apiClient: {
        getKGGraph,
        getKGCommunities,
        getKGGaps,
        updateKGNode,
        createKGEdge,
        deleteKGEdge,
    },
}));

describe('KnowledgeGraph', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getKGGraph.mockResolvedValue(mockGraphData);
        getKGCommunities.mockResolvedValue(mockCommunities);
        getKGGaps.mockResolvedValue(mockGaps);
    });

    it('renders loading state initially', () => {
        render(<KnowledgeGraph />);
        expect(screen.getByText('加载知识图谱...')).toBeDefined();
    });

    it('renders graph after data loads', async () => {
        render(<KnowledgeGraph />);
        await waitFor(() => {
            expect(screen.getByTestId('knowledge-graph')).toBeDefined();
        });
    });

    it('shows node count and edge count stats', async () => {
        render(<KnowledgeGraph />);
        await waitFor(() => {
            // Stats are now shown as separate spans: count + label
            expect(screen.getByText('4')).toBeDefined();
            expect(screen.getByText('概念')).toBeDefined();
            expect(screen.getByText('2')).toBeDefined();
            expect(screen.getByText('关系')).toBeDefined();
        });
    });

    it('calls API with correct user_id', async () => {
        render(<KnowledgeGraph userId={42} />);
        await waitFor(() => {
            expect(getKGGraph).toHaveBeenCalledWith(expect.objectContaining({ userId: 42 }));
            expect(getKGCommunities).toHaveBeenCalledWith(42);
            expect(getKGGaps).toHaveBeenCalledWith(42);
        });
    });

    it('renders gap analysis panel with suggestions', async () => {
        render(<KnowledgeGraph />);
        await waitFor(() => {
            expect(screen.getByTestId('gap-analysis')).toBeDefined();
            expect(screen.getByText('推荐学习')).toBeDefined();
            expect(screen.getByText('Ring Attention')).toBeDefined();
        });
    });

    it('renders graph controls', async () => {
        render(<KnowledgeGraph />);
        await waitFor(() => {
            expect(screen.getByTestId('graph-controls')).toBeDefined();
        });
    });

    it('shows empty state when no graph data', async () => {
        getKGGraph.mockResolvedValue({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 });
        render(<KnowledgeGraph />);
        await waitFor(() => {
            expect(screen.getByTestId('empty-graph')).toBeDefined();
            expect(screen.getByText('尚无知识图谱')).toBeDefined();
        });
    });

    it('shows error state and retry button on API failure', async () => {
        getKGGraph.mockRejectedValue(new Error('Neo4j unavailable'));
        render(<KnowledgeGraph />);
        await waitFor(() => {
            expect(screen.getByText('知识图谱加载失败')).toBeDefined();
            expect(screen.getByText('重试')).toBeDefined();
        });
    });

    it('retries loading on retry button click', async () => {
        getKGGraph.mockRejectedValueOnce(new Error('Neo4j unavailable'));
        render(<KnowledgeGraph />);
        await waitFor(() => {
            expect(screen.getByText('重试')).toBeDefined();
        });
        getKGGraph.mockResolvedValueOnce(mockGraphData);
        fireEvent.click(screen.getByText('重试'));
        await waitFor(() => {
            expect(getKGGraph).toHaveBeenCalledTimes(2);
        });
    });

    it('renders react-flow component with correct node/edge counts', async () => {
        render(<KnowledgeGraph />);
        await waitFor(() => {
            const rf = screen.getByTestId('react-flow');
            expect(rf.getAttribute('data-nodes')).toBe('4');
            expect(rf.getAttribute('data-edges')).toBe('2');
        });
    });
});
