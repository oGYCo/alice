import { Button } from '@/components/ui/button';
import { ThumbsUp, Clock, CheckCircle, ThumbsDown, HelpCircle, MessageCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FeedbackBarProps {
  contentId: number;
  onFeedback: (id: number, type: string) => void;
}

export function FeedbackBar({ contentId, onFeedback }: FeedbackBarProps) {
  const handleFeedback = (type: string) => {
    onFeedback(contentId, type);
  };

  return (
    <div 
      className="fixed bottom-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-t p-4 flex justify-center gap-2 md:gap-4 shadow-lg"
      data-testid="feedback-bar"
    >
      <div className="container flex items-center justify-between max-w-4xl gap-2 overflow-x-auto">
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => handleFeedback('positive')}
            title="高质量"
            className="text-xs md:text-sm"
          >
            <ThumbsUp className="h-4 w-4 mr-1 md:mr-2" />
            <span className="hidden sm:inline">高质量</span>
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => handleFeedback('save_for_later')}
            title="稍后再看"
            className="text-xs md:text-sm"
          >
            <Clock className="h-4 w-4 mr-1 md:mr-2" />
            <span className="hidden sm:inline">稍后再看</span>
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => handleFeedback('seen')}
            title="已知晓"
            className="text-xs md:text-sm"
          >
            <CheckCircle className="h-4 w-4 mr-1 md:mr-2" />
            <span className="hidden sm:inline">已知晓</span>
          </Button>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => handleFeedback('negative')}
            title="无价值"
            className="text-xs md:text-sm text-muted-foreground hover:text-destructive"
          >
            <ThumbsDown className="h-4 w-4 mr-1 md:mr-2" />
            <span className="hidden sm:inline">无价值</span>
          </Button>
        </div>

        <div className="h-6 w-px bg-border mx-2" />

        <div className="flex gap-2">
           <Button 
            variant="secondary" 
            size="sm" 
            onClick={() => handleFeedback('explain_concept')}
            title="解释概念"
            className="text-xs md:text-sm bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-300"
          >
            <HelpCircle className="h-4 w-4 mr-1 md:mr-2" />
            <span className="hidden sm:inline">解释概念</span>
          </Button>
          <Button 
            variant="secondary" 
            size="sm" 
            onClick={() => handleFeedback('ask_followup')}
            title="追问"
            className="text-xs md:text-sm bg-purple-100 text-purple-700 hover:bg-purple-200 dark:bg-purple-900/30 dark:text-purple-300"
          >
            <MessageCircle className="h-4 w-4 mr-1 md:mr-2" />
            <span className="hidden sm:inline">追问</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
