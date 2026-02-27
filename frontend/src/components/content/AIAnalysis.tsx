import { Card, CardHeader, CardContent, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Lightbulb, BrainCircuit, Tag, Clock } from 'lucide-react';
import { ContentDetail } from '@/lib/types';

const CONTENT_TYPE_LABEL: Record<string, string> = {
  knowledge: '知识',
  thought: '观点',
  news: '资讯',
};
const CONTENT_TYPE_VARIANT: Record<string, 'default' | 'secondary' | 'outline'> = {
  knowledge: 'default',
  thought: 'secondary',
  news: 'outline',
};
const DOMAIN_COLORS = [
  'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700',
  'bg-purple-100 text-purple-800 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-700',
  'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-700',
  'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700',
  'bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-300 dark:border-rose-700',
];

interface Props { item: ContentDetail; }

/** AI 概括 卡片 */
export function AISummaryCard({ item }: Props) {
  return (
    <Card className="flex flex-col" data-testid="ai-summary-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-1.5">
          <BrainCircuit className="w-4 h-4 text-primary" />
          AI 概括
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm leading-relaxed text-muted-foreground">
          {item.summary || '暂无概括'}
        </p>
        <div className="flex items-center gap-2 flex-wrap pt-2 border-t border-border/40">
          {item.content_type && (
            <Badge variant={CONTENT_TYPE_VARIANT[item.content_type] ?? 'outline'} className="text-xs">
              {CONTENT_TYPE_LABEL[item.content_type] ?? item.content_type}
            </Badge>
          )}
          {item.estimated_read_time && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="w-3 h-3" />
              约 {item.estimated_read_time} 分钟
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/** 关键要点 卡片 */
export function KeyPointsCard({ item }: Props) {
  return (
    <Card className="flex flex-col" data-testid="key-points-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-1.5">
          <Lightbulb className="w-4 h-4 text-yellow-500" />
          关键要点
        </CardTitle>
      </CardHeader>
      <CardContent>
        {item.key_points && item.key_points.length > 0 ? (
          <ul className="space-y-2">
            {item.key_points.map((point, idx) => (
              <li key={idx} className="flex gap-2 text-sm text-muted-foreground leading-snug">
                <span className="mt-0.5 flex-shrink-0 w-4 h-4 rounded-full bg-primary/10 text-primary text-[10px] flex items-center justify-center font-semibold">
                  {idx + 1}
                </span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">暂无要点</p>
        )}
      </CardContent>
    </Card>
  );
}

/** 领域标签 卡片 */
export function DomainsCard({ item }: Props) {
  return (
    <Card className="h-full flex flex-col" data-testid="domains-card">
      <CardHeader className="pb-2 flex-shrink-0">
        <CardTitle className="text-sm flex items-center gap-1.5">
          <Tag className="w-4 h-4 text-muted-foreground" />
          领域标签
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 overflow-y-auto scrollbar-thin">
        {item.domains && item.domains.length > 0 ? (
          <div className="flex flex-wrap gap-2 content-start">
            {item.domains.map((domain, idx) => (
              <span key={idx} className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${DOMAIN_COLORS[idx % DOMAIN_COLORS.length]}`}>
                {domain}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">暂无标签</p>
        )}
      </CardContent>
    </Card>
  );
}
