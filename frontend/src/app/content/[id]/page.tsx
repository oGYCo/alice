'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { apiClient } from '@/lib/api';
import { ContentDetail } from '@/lib/types';
import { AISummaryCard, KeyPointsCard } from '@/components/content/AIAnalysis';
import { ContentSubgraph } from '@/components/content/ContentSubgraph';
import { OriginalContent } from '@/components/content/OriginalContent';
import { FeedbackBar } from '@/components/content/FeedbackBar';
import { Loader2, AlertCircle } from 'lucide-react';

const isAuthError = (e: unknown) => (e as { status?: number })?.status === 401;

const DOMAIN_TAG_COLORS = [
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-700',
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-900/20 dark:text-purple-300 dark:border-purple-700',
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-700',
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-900/20 dark:text-amber-300 dark:border-amber-700',
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-900/20 dark:text-rose-300 dark:border-rose-700',
];

export default function ContentDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [content, setContent] = useState<ContentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    const fetchContent = async () => {
      try {
        setLoading(true);
        const data = await apiClient.getContentDetail(id);
        setContent(data);
        setError(null);
      } catch (err) {
        if (isAuthError(err)) return;
        setError(err instanceof Error ? err.message : 'Failed to load content.');
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [id]);

  const handleFeedback = async (contentId: number, type: string) => {
    try {
      await apiClient.submitFeedback(contentId, type);
    } catch (err) {
      if (isAuthError(err)) return;
      console.error('Failed to submit feedback:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !content) {
    return (
      <div className="container mx-auto p-4 flex h-screen items-center justify-center">
        <div className="flex w-full max-w-md items-center gap-4 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive shadow-sm">
          <AlertCircle className="h-5 w-5" />
          <div className="flex-1">
            <h5 className="mb-1 font-medium leading-none tracking-tight">Error</h5>
            <div className="text-sm opacity-90">
              {error || 'Content not found.'}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background" data-testid="content-detail-page">
      <div className="max-w-[1040px] mx-auto px-5 lg:px-10 pt-10 pb-24">

        {/* ── Knowledge graph hero (full-width, no card border) ── */}
        {(content.subgraph?.nodes?.length || content.domains?.length) ? (
          <div className="mb-8">
            <ContentSubgraph subgraph={content.subgraph} domains={content.domains} />
          </div>
        ) : null}

        {/* ── Article header ── */}
        <header className="max-w-[740px] mx-auto mb-10">
          {/* Source breadcrumb */}
          <p className="text-[11px] font-semibold tracking-[0.12em] uppercase text-muted-foreground/60 mb-4">
            {content.source}
          </p>
          {/* Title */}
          <h1 className="font-sans text-[30px] lg:text-[38px] font-semibold tracking-tight leading-tight mb-5">
            {content.title}
          </h1>
          {/* Meta row: date · quality score · domain tags */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
            <span>{new Date(content.created_at).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
            {content.quality_score !== null && (
              <>
                <span className="text-border">·</span>
                <span className="inline-flex items-center gap-1">
                  质量分 <strong className="text-foreground tabular-nums">{content.quality_score}</strong>
                </span>
              </>
            )}
            {content.domains && content.domains.length > 0 && (
              <>
                <span className="text-border">·</span>
                <div className="flex flex-wrap gap-1.5">
                  {content.domains.map((d, i) => (
                    <span
                      key={i}
                      className={DOMAIN_TAG_COLORS[i % DOMAIN_TAG_COLORS.length]}
                    >
                      {d}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>
        </header>

        {/* ── AI analysis: 2 cards side by side, aligned with article column ── */}
        <div className="max-w-[740px] mx-auto grid grid-cols-1 md:grid-cols-2 gap-5 mb-10">
          <AISummaryCard item={content} />
          <KeyPointsCard item={content} />
        </div>

        {/* ── Article body ── */}
        <div className="max-w-[960px] mx-auto">
          <hr className="border-border/40 mb-10" />
          <OriginalContent
            content={content.full_content}
            sourceUrl={content.source_url}
          />
        </div>

      </div>

      <FeedbackBar contentId={content.id} onFeedback={handleFeedback} />
    </div>
  );
}
