'use client';

import { memo, useMemo } from 'react';
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
    selected?: boolean;
    onNodeClick?: (nodeId: string) => void;
    [key: string]: unknown;
}

export type ConceptNode = Node<ConceptNodeData>;

// Theme palettes per concept type (light mode friendly, dark mode aware via CSS vars)
const TYPE_THEME: Record<string, {
    gradient: string;
    ring: string;
    icon: string;
    iconBg: string;
    text: string;
    glow: string;
}> = {
    Concept: {
        gradient: 'from-sky-50 to-blue-50 dark:from-sky-950/60 dark:to-blue-950/60',
        ring: 'stroke-sky-500',
        icon: '💡',
        iconBg: 'bg-sky-100 dark:bg-sky-900/50',
        text: 'text-sky-900 dark:text-sky-100',
        glow: 'shadow-sky-400/30 dark:shadow-sky-500/20',
    },
    Method: {
        gradient: 'from-pink-50 to-fuchsia-50 dark:from-pink-950/60 dark:to-fuchsia-950/60',
        ring: 'stroke-pink-500',
        icon: '⚙️',
        iconBg: 'bg-pink-100 dark:bg-pink-900/50',
        text: 'text-pink-900 dark:text-pink-100',
        glow: 'shadow-pink-400/30 dark:shadow-pink-500/20',
    },
    Tool: {
        gradient: 'from-emerald-50 to-green-50 dark:from-emerald-950/60 dark:to-green-950/60',
        ring: 'stroke-emerald-500',
        icon: '🔧',
        iconBg: 'bg-emerald-100 dark:bg-emerald-900/50',
        text: 'text-emerald-900 dark:text-emerald-100',
        glow: 'shadow-emerald-400/30 dark:shadow-emerald-500/20',
    },
    Theory: {
        gradient: 'from-amber-50 to-yellow-50 dark:from-amber-950/60 dark:to-amber-950/60',
        ring: 'stroke-amber-500',
        icon: '📐',
        iconBg: 'bg-amber-100 dark:bg-amber-900/50',
        text: 'text-amber-900 dark:text-amber-100',
        glow: 'shadow-amber-400/30 dark:shadow-amber-500/20',
    },
};

/** Color for the mastery ring arc */
function getMasteryStroke(mastery: number): string {
    if (mastery >= 0.8) return '#22c55e';
    if (mastery >= 0.5) return '#eab308';
    if (mastery >= 0.3) return '#f97316';
    return '#ef4444';
}

/** SVG arc for mastery ring */
function MasteryRing({ mastery, size, heatmapMode, className }: {
    mastery: number;
    size: number;
    heatmapMode?: boolean;
    className?: string;
}) {
    const strokeWidth = 3;
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference * (1 - mastery);
    const color = heatmapMode ? getMasteryStroke(mastery) : getMasteryStroke(mastery);

    return (
        <svg
            width={size}
            height={size}
            className={`absolute inset-0 -rotate-90 ${className ?? ''}`}
            style={{ filter: mastery >= 0.8 ? `drop-shadow(0 0 4px ${color}40)` : undefined }}
        >
            {/* Background track */}
            <circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke="currentColor"
                strokeWidth={strokeWidth}
                className="text-muted/20"
            />
            {/* Mastery arc */}
            <circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={color}
                strokeWidth={strokeWidth}
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                strokeLinecap="round"
                className="transition-all duration-700 ease-out"
            />
        </svg>
    );
}

/** Heatmap background color with opacity progression */
function getHeatmapBg(mastery: number): string {
    if (mastery >= 0.8) return 'bg-green-500/80 dark:bg-green-600/70';
    if (mastery >= 0.5) return 'bg-yellow-400/70 dark:bg-yellow-500/60';
    if (mastery >= 0.3) return 'bg-orange-400/70 dark:bg-orange-500/60';
    return 'bg-red-400/60 dark:bg-red-500/50';
}

// Node base size range: 56–80px scaled by mastery
function getNodeSize(mastery: number): number {
    return 58 + mastery * 22;
}

function ConceptNodeComponent({ data, id }: NodeProps<ConceptNode>) {
    const { name, label, mastery, heatmapMode, isCenter, selected, onNodeClick } = data;

    const theme = TYPE_THEME[label] ?? TYPE_THEME.Concept;
    const size = getNodeSize(mastery);
    const masteryPct = Math.round(mastery * 100);

    // Truncate name to fit in node
    const displayName = useMemo(() => {
        if (name.length <= 8) return name;
        return name.slice(0, 7) + '…';
    }, [name]);

    const centerRing = isCenter
        ? 'ring-2 ring-indigo-500 ring-offset-2 ring-offset-background'
        : '';
    const selectedRing = selected
        ? 'ring-2 ring-primary ring-offset-1 ring-offset-background'
        : '';
    const glowShadow = isCenter ? `shadow-lg ${theme.glow}` : 'shadow-md shadow-black/5 dark:shadow-black/20';

    return (
        <div
            data-testid={`kg-node-${id}`}
            className="concept-node group relative nopan"
            style={{ width: size, height: size }}
            onClick={() => onNodeClick?.(id)}
        >
            <Handle type="target" position={Position.Top} className="!bg-transparent !border-0 !w-2 !h-2" />

            {/* Outer container with mastery ring */}
            <div
                className={`
                    relative flex items-center justify-center rounded-full cursor-pointer
                    transition-all duration-300 ease-out
                    hover:scale-110 hover:shadow-lg
                    ${heatmapMode
                        ? `${getHeatmapBg(mastery)} border border-white/30 dark:border-white/10`
                        : `bg-gradient-to-br ${theme.gradient} border border-black/[0.06] dark:border-white/[0.08]`
                    }
                    ${centerRing} ${selectedRing} ${glowShadow}
                `}
                style={{ width: size, height: size }}
            >
                <MasteryRing mastery={mastery} size={size} heatmapMode={heatmapMode} />

                {/* Center content */}
                <div className="relative z-10 flex flex-col items-center gap-0.5 px-1">
                    <span className="text-sm leading-none select-none">{theme.icon}</span>
                    <span
                        className={`text-[9px] font-semibold leading-tight text-center select-none truncate max-w-[52px] ${
                            heatmapMode ? 'text-white dark:text-white drop-shadow-sm' : theme.text
                        }`}
                    >
                        {displayName}
                    </span>
                </div>

                {/* Mastery badge - top right */}
                <div className={`
                    absolute -top-1 -right-1 z-20
                    flex items-center justify-center
                    w-5 h-5 rounded-full text-[8px] font-bold
                    border border-background
                    ${mastery >= 0.8 ? 'bg-green-500 text-white' :
                      mastery >= 0.5 ? 'bg-yellow-500 text-white' :
                      mastery >= 0.3 ? 'bg-orange-500 text-white' :
                      'bg-red-400 text-white'}
                    shadow-sm transition-transform duration-200 group-hover:scale-110
                `}>
                    {masteryPct}
                </div>
            </div>

            <Handle type="source" position={Position.Bottom} className="!bg-transparent !border-0 !w-2 !h-2" />

            {/* Floating tooltip — appears on hover */}
            <div
                className="absolute -top-[72px] left-1/2 -translate-x-1/2 pointer-events-none
                           opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-50"
                data-testid={`kg-tooltip-${id}`}
            >
                <div className="rounded-xl bg-popover/95 backdrop-blur-sm px-3.5 py-2.5 text-xs shadow-xl
                                border border-border/50 min-w-[140px] text-center">
                    <p className="font-semibold text-popover-foreground leading-snug">{name}</p>
                    <div className="flex items-center justify-center gap-1.5 mt-1 text-muted-foreground">
                        <span className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${theme.iconBg} ${theme.text}`}>
                            {theme.icon} {label}
                        </span>
                        <span className="text-[10px]">·</span>
                        <span className="text-[10px] font-medium" style={{ color: getMasteryStroke(mastery) }}>
                            {masteryPct}%
                        </span>
                    </div>
                    {data.aliases.length > 0 && (
                        <p className="text-muted-foreground/70 mt-1 text-[10px] leading-tight">
                            {data.aliases.slice(0, 3).join(' · ')}
                        </p>
                    )}
                </div>
                <div className="mx-auto h-2 w-2 rotate-45 bg-popover/95 border-b border-r border-border/50 -mt-1" />
            </div>
        </div>
    );
}

export default memo(ConceptNodeComponent);
