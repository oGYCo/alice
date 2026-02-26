import Link from 'next/link';
import { ThumbsUp, Clock, CheckCircle, ThumbsDown } from 'lucide-react';
import { ContentItem } from '@/lib/types';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ContentCardProps {
  item: ContentItem;
  onFeedback: (id: number, type: string) => void;
  viewMode: 'grid' | 'list';
}

const CONTENT_TYPE_LABELS: Record<string, string> = {
  knowledge: '硬核知识',
  thought: '思想性',
  news: '时效信息',
  time_sensitive: '时效信息',
};

const CONTENT_TYPE_COLORS: Record<string, string> = {
  knowledge: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
  thought: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
  news: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300',
  time_sensitive: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300',
};

function formatTimeAgo(dateString: string) {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function ContentCard({ item, onFeedback, viewMode }: ContentCardProps) {
  const isGrid = viewMode === 'grid';

  const typeLabel = item.content_type ? CONTENT_TYPE_LABELS[item.content_type] || item.content_type : 'Unknown';
  const typeColor = item.content_type ? CONTENT_TYPE_COLORS[item.content_type] || 'bg-gray-100 text-gray-800' : 'bg-gray-100 text-gray-800';

  return (
    <Card 
      className={cn(
        "flex overflow-hidden transition-shadow hover:shadow-md", 
        isGrid ? "flex-col h-full" : "flex-row items-stretch h-auto"
      )}
      data-testid="content-card"
    >
      <div className={cn("flex flex-col flex-1", isGrid ? "" : "flex-row")}>
        <div className={cn("flex-1", isGrid ? "" : "flex-row gap-4 p-6")}>
          <CardHeader className={cn("p-4 pb-2 space-y-2", isGrid ? "" : "p-0 pb-0")}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs">
                <span className={cn("px-2 py-0.5 rounded-full font-medium", typeColor)}>
                  {typeLabel}
                </span>
                <span className="text-muted-foreground">{item.source}</span>
                <span className="text-muted-foreground">•</span>
                <span className="text-muted-foreground">{formatTimeAgo(item.created_at)}</span>
              </div>
              {item.quality_score !== null && (
                <div className="flex items-center gap-1 text-xs font-medium" title={`Quality Score: ${item.quality_score}/10`}>
                  <div className="h-1.5 w-16 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-primary" 
                      style={{ width: `${(item.quality_score / 10) * 100}%` }}
                    />
                  </div>
                  <span>{item.quality_score}</span>
                </div>
              )}
            </div>
            
            <Link href={`/content/${item.id}`} className="block group">
              <h3 className="font-semibold text-lg leading-snug group-hover:text-primary transition-colors line-clamp-2">
                {item.title}
              </h3>
            </Link>
          </CardHeader>
          
          <CardContent className={cn("p-4 pt-0 text-sm text-muted-foreground", isGrid ? "" : "p-0 mt-2")}>
            <p className={cn(isGrid ? "line-clamp-3" : "line-clamp-2")}>
              {item.summary || "No summary available."}
            </p>
          </CardContent>
        </div>

        <CardFooter className={cn(
          "p-2 bg-muted/20 flex justify-between gap-1 border-t", 
          isGrid ? "" : "flex-col justify-center border-t-0 border-l w-[140px] shrink-0"
        )}>
           <Button 
            variant="ghost" 
            size="sm" 
            className="flex-1 h-8 px-2 text-xs"
            onClick={() => onFeedback(item.id, 'positive')}
            title="高质量"
          >
            <ThumbsUp className="h-3.5 w-3.5 mr-1.5" />
            <span className={cn(isGrid ? "hidden sm:inline" : "hidden")}>Like</span>
          </Button>
          <Button 
            variant="ghost" 
            size="sm" 
            className="flex-1 h-8 px-2 text-xs"
            onClick={() => onFeedback(item.id, 'save_for_later')}
            title="稍后再看"
          >
            <Clock className="h-3.5 w-3.5 mr-1.5" />
            <span className={cn(isGrid ? "hidden sm:inline" : "hidden")}>Later</span>
          </Button>
          <Button 
            variant="ghost" 
            size="sm" 
            className="flex-1 h-8 px-2 text-xs"
            onClick={() => onFeedback(item.id, 'seen')}
            title="已知晓"
          >
            <CheckCircle className="h-3.5 w-3.5 mr-1.5" />
            <span className={cn(isGrid ? "hidden sm:inline" : "hidden")}>Seen</span>
          </Button>
          <Button 
            variant="ghost" 
            size="sm" 
            className="flex-1 h-8 px-2 text-xs text-muted-foreground hover:text-destructive"
            onClick={() => onFeedback(item.id, 'negative')}
            title="无价值"
          >
            <ThumbsDown className="h-3.5 w-3.5 mr-1.5" />
            <span className={cn(isGrid ? "hidden sm:inline" : "hidden")}>Dislike</span>
          </Button>
        </CardFooter>
      </div>
    </Card>
  );
}
