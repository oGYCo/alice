import { Card, CardHeader, CardContent, CardTitle } from '@/components/ui/card';
import { Lightbulb, BookOpen, BrainCircuit } from 'lucide-react';
import { ContentDetail } from '@/lib/types';

interface AIAnalysisProps {
  item: ContentDetail;
}

export function AIAnalysis({ item }: AIAnalysisProps) {
  return (
    <div className="space-y-6" data-testid="ai-analysis">
      {/* Summary Section */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-primary" />
            AI 核心概括
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {item.summary || "暂无概括"}
          </p>
        </CardContent>
      </Card>

      {/* Key Takeaways */}
      {item.key_takeaways && item.key_takeaways.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Lightbulb className="w-5 h-5 text-yellow-500" />
              关键要点
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-5 space-y-2 text-sm text-muted-foreground">
              {item.key_takeaways.map((takeaway, idx) => (
                <li key={idx}>{takeaway}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Push Reason & Reading Suggestion */}
      <div className="grid gap-4 md:grid-cols-2">
        {item.push_reason && (
          <Card className="bg-muted/50">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                推荐原因
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm">{item.push_reason}</p>
            </CardContent>
          </Card>
        )}

        {item.reading_suggestion && (
          <Card className="bg-muted/50">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <BookOpen className="w-4 h-4" />
                阅读建议
              </CardTitle>
            </CardHeader>
            <CardContent>
              <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">
                {item.reading_suggestion}
              </span>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
