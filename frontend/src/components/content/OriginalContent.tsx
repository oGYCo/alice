import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import { ExternalLink } from 'lucide-react';
import { ArticleRenderer } from './ArticleRenderer';
import 'highlight.js/styles/github-dark.css';

interface OriginalContentProps {
  content: string | null;
  sourceUrl: string;
}

/** Heuristic: if text has markdown headers/bold/code-fences, render as Markdown. */
function looksLikeMarkdown(text: string): boolean {
  return /^#{1,6}\s|\*\*|```|^>\s/m.test(text);
}

export function OriginalContent({ content, sourceUrl }: OriginalContentProps) {
  return (
    <article data-testid="original-content">
      {/* Source link — subtle, top-right */}
      <div className="flex justify-end mb-8">
        <a
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors border border-border/60 rounded-full px-3 py-1.5 hover:border-border"
        >
          <ExternalLink className="w-3 h-3" />
          阅读原文
        </a>
      </div>

      {content ? (
        looksLikeMarkdown(content) ? (
          <div className="prose prose-lg dark:prose-invert max-w-none prose-headings:font-bold prose-headings:tracking-tight prose-p:leading-[1.85] prose-p:text-foreground/85">
            <ReactMarkdown rehypePlugins={[rehypeHighlight]}>{content}</ReactMarkdown>
          </div>
        ) : (
          <ArticleRenderer text={content} />
        )
      ) : (
        <div className="flex flex-col items-center justify-center py-24 text-muted-foreground gap-4">
          <p className="text-sm">原文内容暂不可用</p>
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-primary hover:underline"
          >
            前往原始链接阅读 →
          </a>
        </div>
      )}
    </article>
  );
}

