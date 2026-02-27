'use client';

import { memo, useMemo, type CSSProperties } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';

// Types for concept nodes
export interface ConceptNodeData {
    name: string;
    label: string; // Concept | Method | Tool | Theory
    mastery: number;
    communityId: number | null;
    aliases: string[];
    isCenter?: boolean;
    heatmapMode?: boolean;
    onNodeClick?: (nodeId: string) => void;
    [key: string]: unknown;
}

export type ConceptNode = Node<ConceptNodeData>;

// Color mapping by concept type
const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
    Concept: { bg: '#e0f2fe', border: '#0284c7', text: '#0c4a6e' },
    Method: { bg: '#fce7f3', border: '#db2777', text: '#831843' },
    Tool: { bg: '#dcfce7', border: '#16a34a', text: '#14532d' },
    Theory: { bg: '#fef3c7', border: '#d97706', text: '#78350f' },
};

// Mastery heatmap colors
function getMasteryColor(mastery: number): string {
    if (mastery >= 0.8) return '#22c55e'; // green — mastered
    if (mastery >= 0.5) return '#eab308'; // yellow — learning
    if (mastery >= 0.3) return '#f97316'; // orange — aware
    return '#ef4444'; // red — unknown
}

function getMasteryOpacity(mastery: number): number {
    return 0.4 + mastery * 0.6; // 0.4 to 1.0
}

// Node size based on mastery
function getNodeSize(mastery: number): number {
    return 40 + mastery * 30; // 40px to 70px
}

const TYPE_ICONS: Record<string, string> = {
    Concept: '💡',
    Method: '⚙️',
    Tool: '🔧',
    Theory: '📐',
};

function ConceptNodeComponent({ data, id }: NodeProps<ConceptNode>) {
    const { name, label, mastery, heatmapMode, isCenter, onNodeClick } = data;

    const typeColor = TYPE_COLORS[label] ?? TYPE_COLORS.Concept;
    const size = getNodeSize(mastery);
    const masteryPct = Math.round(mastery * 100);

    const style = useMemo<CSSProperties>(() => {
        if (heatmapMode) {
            const heatColor = getMasteryColor(mastery);
            return {
                width: size,
                height: size,
                borderRadius: '50%',
                backgroundColor: heatColor,
                opacity: getMasteryOpacity(mastery),
                border: isCenter ? '3px solid #6366f1' : '2px solid transparent',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
            };
        }
        return {
            width: size,
            height: size,
            borderRadius: '50%',
            backgroundColor: typeColor.bg,
            border: isCenter ? `3px solid #6366f1` : `2px solid ${typeColor.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            boxShadow: isCenter ? '0 0 12px rgba(99, 102, 241, 0.4)' : '0 1px 3px rgba(0,0,0,0.1)',
        };
    }, [heatmapMode, mastery, size, isCenter, typeColor]);

    return (
        <div
            data-testid={`kg-node-${id}`}
            className="concept-node group relative"
            style={style}
            onClick={() => onNodeClick?.(id)}
        >
            <Handle type="target" position={Position.Top} style={{ visibility: 'hidden' }} />
            <span className="text-xs select-none" style={{ color: heatmapMode ? '#fff' : typeColor.text }}>
                {TYPE_ICONS[label] ?? '💡'}
            </span>
            <Handle type="source" position={Position.Bottom} style={{ visibility: 'hidden' }} />

            {/* Tooltip */}
            <div
                className="absolute -top-20 left-1/2 -translate-x-1/2 hidden group-hover:flex flex-col items-center z-50"
                data-testid={`kg-tooltip-${id}`}
            >
                <div className="rounded-lg bg-popover px-3 py-2 text-xs shadow-lg border min-w-[120px] text-center">
                    <p className="font-semibold text-popover-foreground">{name}</p>
                    <p className="text-muted-foreground mt-0.5">{label} · {masteryPct}%</p>
                    {data.aliases.length > 0 && (
                        <p className="text-muted-foreground mt-0.5 text-[10px]">{data.aliases.slice(0, 3).join(', ')}</p>
                    )}
                </div>
                <div className="h-2 w-2 rotate-45 bg-popover border-b border-r -mt-1" />
            </div>
        </div>
    );
}

export default memo(ConceptNodeComponent);
