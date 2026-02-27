'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { ContentItem } from '@/lib/types';
import { FeedHeader } from '@/components/feed/FeedHeader';
import { ContentCard } from '@/components/feed/ContentCard';
import { FeedSkeleton } from '@/components/feed/FeedSkeleton';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Trash2, CheckSquare, Square, X } from 'lucide-react';

/** Returns true when the error is a 401 — handled globally by AuthGuard, no UI needed. */
const isAuthError = (e: unknown) => (e as { status?: number })?.status === 401;

export default function FeedPage() {
  const [items, setItems] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hasSources, setHasSources] = useState(false);
  const [triggeringFetch, setTriggeringFetch] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [sortBy, setSortBy] = useState('relevance');
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);

  const observerTarget = useRef<HTMLDivElement>(null);
  const autoFetchAttempted = useRef(false);

  const loadSources = useCallback(async () => {
    try {
      const sources = await apiClient.getSources();
      setHasSources(sources.length > 0);
    } catch {
      setHasSources(false);
    }
  }, []);

  const loadFeed = useCallback(async (pageNum: number, currentSort: string, isReset = false) => {
    try {
      setLoading(true);
      const newItems = await apiClient.getFeed(pageNum, 20, currentSort);
      setLoadError(null);
      setItems(prev => isReset ? newItems : [...prev, ...newItems]);
      setHasMore(newItems.length === 20);
    } catch (error) {
      if (isAuthError(error)) return; // AuthGuard will redirect to /login
      const message = error instanceof Error ? error.message : 'Failed to load feed';
      setLoadError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Reset and load when sort changes
  useEffect(() => {
    setPage(1);
    loadFeed(1, sortBy, true);
  }, [sortBy, loadFeed]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

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
    } catch (error) {
      if (isAuthError(error)) return;
      console.error('Failed to submit feedback:', error);
    }
  };

  const handleDelete = useCallback(async (id: number) => {
    try {
      await apiClient.deleteContent(id);
      setPage(1);
      await loadFeed(1, sortBy, true);
    } catch (error) {
      if (isAuthError(error)) return;
      console.error('Failed to delete content:', error);
    }
  }, [loadFeed, sortBy]);

  const handleBatchDelete = useCallback(async () => {
    if (selectedIds.size === 0) return;
    setIsDeleting(true);
    try {
      const ids = Array.from(selectedIds);
      await apiClient.deleteContentBatch(ids);
      setSelectedIds(new Set());
      setSelectMode(false);
      setPage(1);
      await loadFeed(1, sortBy, true);
    } catch (error) {
      if (isAuthError(error)) return;
      console.error('Failed to batch delete content:', error);
    } finally {
      setIsDeleting(false);
    }
  }, [selectedIds, loadFeed, sortBy]);

  const handleToggleSelect = useCallback((id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelectedIds(new Set(items.map(i => i.id)));
  }, [items]);

  const handleExitSelectMode = useCallback(() => {
    setSelectMode(false);
    setSelectedIds(new Set());
  }, []);

  const handleFetchNow = useCallback(async () => {
    try {
      setTriggeringFetch(true);
      setLoadError(null);
      await apiClient.triggerFetch();
      setPage(1);
      await loadFeed(1, sortBy, true);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to trigger fetch';
      setLoadError(message);
    } finally {
      setTriggeringFetch(false);
    }
  }, [loadFeed, sortBy]);

  useEffect(() => {
    if (!loading && items.length === 0 && hasSources && !autoFetchAttempted.current && !triggeringFetch) {
      autoFetchAttempted.current = true;
      void handleFetchNow();
    }
  }, [handleFetchNow, hasSources, items.length, loading, triggeringFetch]);

  return (
    <div className="container py-6 space-y-6 h-full flex flex-col max-w-7xl mx-auto">
      <FeedHeader
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        sortBy={sortBy}
        onSortChange={setSortBy}
        selectMode={selectMode}
        onToggleSelectMode={() => selectMode ? handleExitSelectMode() : setSelectMode(true)}
      />

      {/* Bulk action bar */}
      {selectMode && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 px-4 py-2 text-sm">
          <span className="text-muted-foreground flex-1">
            {selectedIds.size} selected
          </span>
          <Button variant="ghost" size="sm" onClick={handleSelectAll} className="gap-1.5 h-8">
            <CheckSquare className="h-3.5 w-3.5" />
            Select All
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setSelectedIds(new Set())} className="gap-1.5 h-8">
            <Square className="h-3.5 w-3.5" />
            Deselect All
          </Button>
          <Button
            variant="destructive"
            size="sm"
            disabled={selectedIds.size === 0 || isDeleting}
            onClick={handleBatchDelete}
            className="gap-1.5 h-8"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {isDeleting ? 'Deleting...' : `Delete (${selectedIds.size})`}
          </Button>
          <Button variant="ghost" size="sm" onClick={handleExitSelectMode} className="h-8 w-8 p-0">
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}

      {loadError && (
        <div
          data-testid="feed-error"
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {loadError}
        </div>
      )}

      {loading && page === 1 ? (
        <FeedSkeleton />
      ) : items.length === 0 && !loading ? (
        <div data-testid="empty-state" className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground border-2 border-dashed rounded-lg">
          <p className="text-lg font-medium">No content yet</p>
          {hasSources ? (
            <>
              <p className="text-sm">Sources are configured but no content has been fetched yet.</p>
              <Button
                type="button"
                className="mt-4"
                onClick={handleFetchNow}
                disabled={triggeringFetch}
                data-testid="fetch-now"
              >
                {triggeringFetch ? 'Fetching...' : 'Fetch Now'}
              </Button>
            </>
          ) : (
            <p className="text-sm">Add sources in Settings to get started</p>
          )}
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
              onDelete={handleDelete}
              viewMode={viewMode}
              isSelectMode={selectMode}
              isSelected={selectedIds.has(item.id)}
              onToggleSelect={handleToggleSelect}
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
