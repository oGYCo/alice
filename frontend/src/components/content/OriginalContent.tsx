import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import { buttonVariants } from '@/components/ui/button';
import { ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import 'highlight.js/styles/github-dark.css';

interface OriginalContentProps {
  content: string;
  sourceUrl: string;
}

export function OriginalContent({ content, sourceUrl }: OriginalContentProps) {
  return (
    <div className="space-y-4" data-testid="original-content">
      <div className="flex justify-end">
        <a 
          href={sourceUrl} 
          target="_blank" 
          rel="noopener noreferrer" 
          className={cn(buttonVariants({ variant: "outline", size: "sm" }), "flex items-center gap-2")}
        >
          <ExternalLink className="w-4 h-4" />
          Open Original
        </a>
      </div>
      
      <div className="prose prose-sm md:prose-base lg:prose-lg dark:prose-invert max-w-none">
        <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
