'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { apiClient } from '@/lib/api';
import { ContentDetail } from '@/lib/types';
import { AIAnalysis } from '@/components/content/AIAnalysis';
import { ContentSubgraph } from '@/components/content/ContentSubgraph';
import { OriginalContent } from '@/components/content/OriginalContent';
import { FeedbackBar } from '@/components/content/FeedbackBar';
import { Loader2, AlertCircle } from 'lucide-react';

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
        console.error('Failed to fetch content detail:', err);
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
      // Optional: Show success toast or update UI state
      console.log(`Feedback ${type} submitted for ${contentId}`);
    } catch (err) {
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
    <div className="min-h-screen bg-background pb-20" data-testid="content-detail-page">
      <div className="container mx-auto p-4 lg:p-8">
        <header className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight lg:text-3xl mb-2">{content.title}</h1>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>{content.source}</span>
            <span>•</span>
            <span>{new Date(content.created_at).toLocaleDateString()}</span>
            {content.quality_score !== null && (
              <>
                <span>•</span>
                <span className="font-medium text-foreground">Score: {content.quality_score}</span>
              </>
            )}
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Panel: AI Analysis & Graph */}
          <div className="lg:col-span-1 space-y-6">
            <AIAnalysis item={content} />
            <ContentSubgraph subgraph={content.subgraph} />
          </div>

          {/* Middle/Right Panel: Original Content */}
          <div className="lg:col-span-2">
            <OriginalContent 
              content={content.full_content || content.summary || "No content available."} 
              sourceUrl={content.url} 
            />
          </div>
        </div>
      </div>

      <FeedbackBar contentId={content.id} onFeedback={handleFeedback} />
    </div>
  );
}
