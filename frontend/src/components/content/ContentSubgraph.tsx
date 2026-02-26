import React, { useMemo } from 'react';
import { ContentSubgraph as ContentSubgraphType } from '@/lib/types';
import { cn } from '@/lib/utils';

interface ContentSubgraphProps {
  subgraph: ContentSubgraphType | null;
}

export function ContentSubgraph({ subgraph }: ContentSubgraphProps) {
  const width = 600;
  const height = 400;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) / 3;

  const graphData = useMemo(() => {
    if (!subgraph || !subgraph.nodes.length) return { nodes: [], edges: [] };

    const nodeCount = subgraph.nodes.length;
    const angleStep = (2 * Math.PI) / nodeCount;

    const nodesWithPos = subgraph.nodes.map((node, index) => {
      const angle = index * angleStep;
      return {
        ...node,
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      };
    });

    const edgesWithPos = subgraph.edges.map((edge) => {
      const sourceNode = nodesWithPos.find((n) => n.id === edge.from);
      const targetNode = nodesWithPos.find((n) => n.id === edge.to);
      return {
        ...edge,
        source: sourceNode,
        target: targetNode,
      };
    }).filter(e => e.source && e.target);

    return { nodes: nodesWithPos, edges: edgesWithPos };
  }, [subgraph, centerX, centerY, radius]);

  if (!subgraph || subgraph.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-muted/20 rounded-lg text-muted-foreground" data-testid="content-subgraph">
        暂无相关概念图谱
      </div>
    );
  }

  const getMasteryClass = (mastery: number) => {
    if (mastery >= 0.8) return "fill-green-500 stroke-green-700 text-green-700";
    if (mastery >= 0.4) return "fill-yellow-400 stroke-yellow-600 text-yellow-700";
    return "fill-gray-300 stroke-gray-500 text-gray-600";
  };

  return (
    <div className="w-full h-full min-h-[400px] border rounded-lg bg-white dark:bg-slate-950 overflow-hidden relative" data-testid="content-subgraph">
      <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="28" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" className="fill-gray-400" />
          </marker>
        </defs>

        {/* Edges */}
        {graphData.edges.map((edge, i) => (
          <g key={`edge-${i}`}>
            <line
              x1={edge.source!.x}
              y1={edge.source!.y}
              x2={edge.target!.x}
              y2={edge.target!.y}
              className="stroke-gray-300 stroke-2"
              markerEnd="url(#arrowhead)"
            />
             {/* Optional: Edge Labels (simple midpoint) */}
             {/* <text x={(edge.source!.x + edge.target!.x)/2} y={(edge.source!.y + edge.target!.y)/2} className="text-[10px] fill-gray-500">{edge.relation}</text> */}
          </g>
        ))}

        {/* Nodes */}
        {graphData.nodes.map((node) => (
          <g key={node.id} className="concept-node cursor-pointer hover:opacity-80 transition-opacity">
            <circle
              cx={node.x}
              cy={node.y}
              r="20"
              className={cn("stroke-2", getMasteryClass(node.mastery))}
              data-testid={`node-${node.id}`}
            />
            <text
              x={node.x}
              y={node.y + 35}
              textAnchor="middle"
              className="text-xs font-medium fill-current dark:fill-white"
            >
              {node.label}
            </text>
            <title>{node.label} (Mastery: {Math.round(node.mastery * 100)}%)</title>
          </g>
        ))}
      </svg>
    </div>
  );
}
