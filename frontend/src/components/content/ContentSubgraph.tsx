'use client';

import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  type NodeTypes,
  type Node,
  type Edge,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { ContentSubgraph as ContentSubgraphType } from '@/lib/types';
import { cn } from '@/lib/utils';

/* ─── props ──────────────────────────────────────────────────────────────── */
interface ContentSubgraphProps {
  subgraph: ContentSubgraphType | null;
  domains?: string[] | null;
  label?: string;
}

/* ─── domain tag palette ─────────────────────────────────────────────────── */
const DOMAIN_COLORS = [
  'bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-700',
  'bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-900/20 dark:text-purple-300 dark:border-purple-700',
  'bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-700',
  'bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-900/20 dark:text-amber-800/80 dark:border-amber-700',
  'bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-900/20 dark:text-rose-300 dark:border-rose-700',
  'bg-sky-50 text-sky-700 border border-sky-200 dark:bg-sky-900/20 dark:text-sky-300 dark:border-sky-700',
];

/* ─── node data type ─────────────────────────────────────────────────────── */
type KgNodeData = { name: string; label: string; mastery: number };

/* ─── mastery accent color ───────────────────────────────────────────────── */
function masteryAccent(m: number): { dot: string; ring: string; label: string } {
  if (m >= 0.8) return { dot: '#22c55e', ring: 'rgba(34,197,94,0.30)', label: '精通' };
  if (m >= 0.5) return { dot: '#f59e0b', ring: 'rgba(245,158,11,0.25)', label: '熟悉' };
  return { dot: '#94a3b8', ring: 'rgba(148,163,184,0.18)', label: '了解' };
}

/* ─── glass-card node ────────────────────────────────────────────────────── */
function KnowledgeNode({ data }: NodeProps) {
  const d = data as KgNodeData;
  const acc = masteryAccent(d.mastery);

  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.82)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        border: '1px solid rgba(255,255,255,0.9)',
        borderRadius: 12,
        boxShadow: `0 2px 12px rgba(0,0,0,0.08), 0 0 0 1.5px ${acc.ring}, inset 0 1px 0 rgba(255,255,255,0.8)`,
        minWidth: 80,
        maxWidth: 140,
        padding: '8px 14px 9px',
        cursor: 'grab',
        userSelect: 'none',
        position: 'relative',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0, pointerEvents: 'none' }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, pointerEvents: 'none' }} />

      {/* mastery dot */}
      <div style={{
        position: 'absolute',
        top: 7,
        right: 9,
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: acc.dot,
        boxShadow: `0 0 6px ${acc.dot}`,
      }} />

      {/* category label */}
      <div style={{
        fontSize: 9,
        fontWeight: 500,
        color: '#94a3b8',
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        marginBottom: 3,
        lineHeight: 1,
      }}>
        {d.label || acc.label}
      </div>

      {/* name */}
      <div style={{
        color: '#0f172a',
        fontWeight: 650,
        fontSize: 12.5,
        lineHeight: 1.35,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}>
        {d.name}
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = { knowledge: KnowledgeNode };

/* ─── circle seed ────────────────────────────────────────────────────────── */
function circleLayout(count: number) {
  const r = count <= 1 ? 0 : Math.max(110, count * 22);
  return Array.from({ length: count }, (_, i) => {
    const a = (2 * Math.PI * i) / Math.max(count, 1) - Math.PI / 2;
    return { x: r * Math.cos(a) - 55, y: r * Math.sin(a) - 20 };
  });
}

/* ─── component ──────────────────────────────────────────────────────────── */
export function ContentSubgraph({ subgraph, domains, label = '知识图谱' }: ContentSubgraphProps) {
  const initialNodes = useMemo<Node[]>(() => {
    if (!subgraph?.nodes.length) return [];
    const positions = circleLayout(subgraph.nodes.length);
    return subgraph.nodes.map((n, i) => ({
      id: n.id,
      type: 'knowledge',
      position: positions[i],
      data: { name: n.name, label: n.label, mastery: n.mastery } as KgNodeData,
    }));
  }, [subgraph]);

  const initialEdges = useMemo<Edge[]>(() => {
    if (!subgraph?.edges.length) return [];
    return subgraph.edges.map((e, i) => ({
      id: `e-${i}`,
      source: e.from,
      target: e.to,
      label: e.relation || undefined,
      type: 'smoothstep',
      animated: true,
      style: { stroke: 'rgba(139,92,246,0.45)', strokeWidth: 1.5, strokeDasharray: '5,3' },
      labelStyle: { fontSize: 9, fill: '#a78bfa', fontWeight: 500 },
      labelBgStyle: { fill: 'rgba(139,92,246,0.07)', borderRadius: 4 },
      labelBgPadding: [3, 5] as [number, number],
      markerEnd: { type: 'arrowclosed', color: 'rgba(139,92,246,0.5)', width: 12, height: 12 } as Edge['markerEnd'],
    }));
  }, [subgraph]);

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  /* ── Case 1: real graph ─────────────────────────────────────────────── */
  if (initialNodes.length > 0) {
    return (
      <div
        className="w-full rounded-2xl overflow-hidden relative"
        style={{
          height: 320,
          background: 'linear-gradient(145deg, #f0f4ff 0%, #faf5ff 50%, #f0fdf4 100%)',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.8), 0 1px 3px rgba(0,0,0,0.06)',
          border: '1px solid rgba(139,92,246,0.12)',
        }}
        data-testid="content-subgraph"
      >
        {/* header */}
        <div className="absolute top-0 left-0 right-0 z-20 flex items-center gap-2 px-4 pt-3 pb-0 pointer-events-none select-none">
          <span className="text-[10px] font-semibold tracking-[0.14em] uppercase text-violet-400/80">
            {label}
          </span>
          <div className="flex-1 h-px bg-gradient-to-r from-violet-200/60 to-transparent" />
          <span className="text-[10px] text-slate-400/70">{initialNodes.length} 个节点</span>
        </div>

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.22 }}
          minZoom={0.35}
          maxZoom={2.5}
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
          style={{ background: 'transparent' }}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={18}
            size={1}
            color="rgba(139,92,246,0.12)"
          />
          <Controls
            showInteractive={false}
            style={{
              bottom: 12,
              right: 12,
              top: 'auto',
              left: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          />
        </ReactFlow>

        <style>{`
          .react-flow__attribution { display: none !important; }
          .react-flow__controls {
            background: rgba(255,255,255,0.85) !important;
            border: 1px solid rgba(139,92,246,0.15) !important;
            border-radius: 10px !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
            padding: 3px !important;
          }
          .react-flow__controls-button {
            background: transparent !important;
            border: none !important;
            border-radius: 7px !important;
            color: #7c3aed !important;
            width: 24px !important;
            height: 24px !important;
          }
          .react-flow__controls-button:hover {
            background: rgba(139,92,246,0.10) !important;
          }
          .react-flow__controls-button svg { fill: #7c3aed; }
          .react-flow__edge-path { filter: drop-shadow(0 0 3px rgba(139,92,246,0.25)); }
        `}</style>
      </div>
    );
  }

  /* ── Case 2: domain tags only ───────────────────────────────────────── */
  if (domains && domains.length > 0) {
    return (
      <div
        className="w-full rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-100 dark:border-slate-800 px-5 py-5 flex flex-wrap gap-2 items-center"
        data-testid="content-subgraph"
      >
        <span className="text-[11px] font-semibold tracking-widest uppercase text-muted-foreground/50 mr-1 select-none">
          {label}
        </span>
        {domains.map((d, i) => (
          <span
            key={i}
            className={cn(
              'inline-flex items-center rounded-full px-3 py-1 text-sm font-medium',
              DOMAIN_COLORS[i % DOMAIN_COLORS.length],
            )}
          >
            {d}
          </span>
        ))}
      </div>
    );
  }

  /* ── Case 3: nothing ─────────────────────────────────────────────────── */
  return null;
}
