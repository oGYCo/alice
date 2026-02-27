'use client';

import React, { useState } from 'react';
import { ThumbsUp, Clock, CheckCircle2, ThumbsDown, Lightbulb, MessageCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FeedbackBarProps {
  contentId: number;
  onFeedback: (id: number, type: string) => void;
}

const ACTIONS = [
  {
    type: 'positive',
    icon: ThumbsUp,
    label: '高质量',
    color: 'hover:bg-emerald-50 hover:text-emerald-600 dark:hover:bg-emerald-900/30 dark:hover:text-emerald-400',
    activeColor: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400',
  },
  {
    type: 'save_for_later',
    icon: Clock,
    label: '稍后看',
    color: 'hover:bg-blue-50 hover:text-blue-600 dark:hover:bg-blue-900/30 dark:hover:text-blue-400',
    activeColor: 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
  },
  {
    type: 'seen',
    icon: CheckCircle2,
    label: '已知晓',
    color: 'hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-200',
    activeColor: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
  },
  {
    type: 'explain_concept',
    icon: Lightbulb,
    label: '解释',
    color: 'hover:bg-amber-50 hover:text-amber-600 dark:hover:bg-amber-900/30 dark:hover:text-amber-400',
    activeColor: 'bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400',
  },
  {
    type: 'ask_followup',
    icon: MessageCircle,
    label: '追问',
    color: 'hover:bg-purple-50 hover:text-purple-600 dark:hover:bg-purple-900/30 dark:hover:text-purple-400',
    activeColor: 'bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
  },
  {
    type: 'negative',
    icon: ThumbsDown,
    label: '无价值',
    color: 'hover:bg-rose-50 hover:text-rose-500 dark:hover:bg-rose-900/30 dark:hover:text-rose-400',
    activeColor: 'bg-rose-50 text-rose-500 dark:bg-rose-900/30 dark:text-rose-400',
  },
];

export function FeedbackBar({ contentId, onFeedback }: FeedbackBarProps) {
  const [active, setActive] = useState<string | null>(null);

  const handleClick = (type: string) => {
    setActive(type);
    onFeedback(contentId, type);
  };

  return (
    <div
      className="fixed right-5 top-1/2 -translate-y-1/2 z-50 flex flex-col items-center gap-1 p-1.5 rounded-2xl bg-background/80 backdrop-blur-md border border-border/60 shadow-lg shadow-black/5"
      data-testid="feedback-bar"
    >
      {ACTIONS.map(({ type, icon: Icon, label, color, activeColor }, idx) => (
        <React.Fragment key={type}>
          {/* divider before the last item (negative) */}
          {idx === ACTIONS.length - 1 && (
            <div className="w-5 h-px bg-border/60 my-0.5" />
          )}
          <button
            onClick={() => handleClick(type)}
            title={label}
            className={cn(
              'group relative flex flex-col items-center justify-center w-10 h-10 rounded-xl transition-all duration-150',
              'text-muted-foreground/60',
              color,
              active === type && activeColor,
            )}
          >
            <Icon className="h-4 w-4" strokeWidth={active === type ? 2.5 : 1.8} />
            {/* tooltip */}
            <span className="pointer-events-none absolute right-full mr-2.5 whitespace-nowrap rounded-lg bg-popover border border-border/60 px-2 py-1 text-[11px] font-medium text-popover-foreground shadow-md opacity-0 group-hover:opacity-100 transition-opacity duration-150">
              {label}
            </span>
          </button>
        </React.Fragment>
      ))}
    </div>
  );
}
