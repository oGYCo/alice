import { LayoutGrid, List } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface FeedHeaderProps {
  viewMode: 'grid' | 'list';
  onViewModeChange: (mode: 'grid' | 'list') => void;
  sortBy: string;
  onSortChange: (sort: string) => void;
}

export function FeedHeader({
  viewMode,
  onViewModeChange,
  sortBy,
  onSortChange,
}: FeedHeaderProps) {
  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6" data-testid="feed-header">
      <h1 className="text-3xl font-bold tracking-tight">Feed</h1>
      
      <div className="flex items-center gap-4 w-full sm:w-auto">
        <select
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value)}
          className="h-9 w-full sm:w-[180px] rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="relevance">Relevance</option>
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
        </select>

        <div className="flex items-center rounded-md border bg-muted/50 p-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onViewModeChange('grid')}
            className={cn(
              "h-7 w-7 p-0 hover:bg-background",
              viewMode === 'grid' && "bg-background shadow-sm"
            )}
          >
            <LayoutGrid className="h-4 w-4" />
            <span className="sr-only">Grid view</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onViewModeChange('list')}
            className={cn(
              "h-7 w-7 p-0 hover:bg-background",
              viewMode === 'list' && "bg-background shadow-sm"
            )}
          >
            <List className="h-4 w-4" />
            <span className="sr-only">List view</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
