'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { ContentItem } from '@/lib/types';
import { FeedHeader } from '@/components/feed/FeedHeader';
import { ContentCard } from '@/components/feed/ContentCard';
import { FeedSkeleton } from '@/components/feed/FeedSkeleton';
import { cn } from '@/lib/utils';

export default function FeedPage() {
  const [items, setItems] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [sortBy, setSortBy] = useState('relevance');
  
  const observerTarget = useRef<HTMLDivElement>(null);

  const loadFeed = useCallback(async (pageNum: number, currentSort: string, isReset = false) => {
    try {
      setLoading(true);
      const newItems = await apiClient.getFeed(pageNum, 20, currentSort);
      
      setItems(prev => isReset ? newItems : [...prev, ...newItems]);
      setHasMore(newItems.length === 20);
    } catch (error) {
      console.error('Failed to load feed:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Reset and load when sort changes
  useEffect(() => {
    setPage(1);
    loadFeed(1, sortBy, true);
  }, [sortBy, loadFeed]);

  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading) {
          setPage(prev => {
            const nextPage = prev + 1;
            loadFeed(nextPage, sortBy, false);
            return nextPage;
          });
        }
      },
      { threshold: 1.0 }
    );

    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }

    return () => observer.disconnect();
  }, [hasMore, loading, sortBy, loadFeed]);

  const handleFeedback = async (id: number, type: string) => {
    try {
      await apiClient.submitFeedback(id, type);
      console.log(`Feedback ${type} submitted for ${id}`);
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  return (
    <div className="container py-6 space-y-6 h-full flex flex-col max-w-7xl mx-auto">
      <FeedHeader 
        viewMode={viewMode} 
        onViewModeChange={setViewMode}
        sortBy={sortBy}
        onSortChange={setSortBy}
      />

      {loading && page === 1 ? (
        <FeedSkeleton />
      ) : items.length === 0 && !loading ? (
        <div data-testid="empty-state" className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground border-2 border-dashed rounded-lg">
          <p className="text-lg font-medium">No content yet</p>
          <p className="text-sm">Add sources in Settings to get started</p>
        </div>
      ) : (
        <div className={cn(
          "grid gap-4 pb-8",
          viewMode === 'grid' 
            ? "grid-cols-1 md:grid-cols-2 xl:grid-cols-3" 
            : "grid-cols-1"
        )}>
          {items.map((item) => (
            <ContentCard 
              key={`${item.id}-${item.pipeline_status}`} 
              item={item} 
              onFeedback={handleFeedback}
              viewMode={viewMode}
            />
          ))}
          {loading && page > 1 && (
            <div className="col-span-full py-4 text-center text-muted-foreground animate-pulse">
              Loading more content...
            </div>
          )}
        </div>
      )}
      
      {/* Sentinel for infinite scroll */}
      <div ref={observerTarget} className="h-4 w-full" />
    </div>
  );
}

