import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import { ExternalLink } from 'lucide-react';
import { ArticleRenderer } from './ArticleRenderer';
import 'highlight.js/styles/github-dark.css';
import { cn } from '@/lib/utils';

interface OriginalContentProps {
  content: string | null;
  sourceUrl: string;
}

const MARKDOWN_SIGNAL = /^#{1,6}\s|^\s*[-*+]\s+|^\s*\d+[.)]\s+|```|^\s*>\s/m;

function decodeEntities(text: string): string {
  if (typeof window === 'undefined') return text;
  const textarea = document.createElement('textarea');
  textarea.innerHTML = text;
  return textarea.value;
}

function normalizeContent(content: string): string {
  const normalized = content.replace(/\r\n?/g, '\n').trim();
  if (!normalized) return '';

  if (!/<[a-z][\s\S]*>/i.test(normalized)) {
    return normalized.replace(/\n{3,}/g, '\n\n');
  }

  const asText = normalized
    .replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|section|article|h[1-6]|blockquote|pre)>/gi, '\n\n')
    .replace(/<\/(li|ul|ol)>/gi, '\n')
    .replace(/<li[^>]*>/gi, '- ')
    .replace(/<[^>]+>/g, '');

  return decodeEntities(asText)
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function looksLikeMarkdown(text: string): boolean {
  return MARKDOWN_SIGNAL.test(text);
}

export function OriginalContent({ content, sourceUrl }: OriginalContentProps) {
  const normalized = content ? normalizeContent(content) : '';
  const renderAsMarkdown = normalized ? looksLikeMarkdown(normalized) : false;

  return (
    <article data-testid="original-content" className="pb-12">
      <div className="mb-11 flex items-center justify-between border-y border-zinc-200/80 py-4 dark:border-zinc-800/90">
        <span className="text-[0.7rem] uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
          Original Text
        </span>
        <a
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300/80 px-3 py-1.5 text-xs text-zinc-600 transition-colors hover:border-zinc-500 hover:text-zinc-900 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-zinc-500 dark:hover:text-zinc-50"
        >
          <ExternalLink className="w-3 h-3" />
          阅读原文
        </a>
      </div>

      {normalized ? (
        <div className="rounded-[22px] border border-zinc-200/75 bg-gradient-to-b from-white to-zinc-50/45 px-7 py-9 shadow-[0_1px_0_rgba(0,0,0,0.03)] md:px-14 md:py-12 dark:border-zinc-800 dark:from-zinc-950 dark:to-zinc-900/45">
          {renderAsMarkdown ? (
            <div>
              <ReactMarkdown
                rehypePlugins={[rehypeHighlight]}
                components={{
                  h1: ({ children }) => (
                    <h1 className="mt-0 mb-8 font-serif text-[2.45rem] leading-[1.12] tracking-[-0.02em] text-[#0f0f0f] dark:text-zinc-50">
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="mt-14 mb-5 font-serif text-[2rem] leading-[1.16] tracking-[-0.014em] text-[#111111] dark:text-zinc-50">
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="mt-12 mb-4 font-serif text-[1.52rem] leading-[1.22] tracking-[-0.01em] text-[#121212] dark:text-zinc-50">
                      {children}
                    </h3>
                  ),
                  p: ({ children }) => (
                    <p className="mb-8 font-serif text-[1.17rem] leading-[1.92] tracking-[0.002em] text-[#232323] dark:text-zinc-200">
                      {children}
                    </p>
                  ),
                  ul: ({ children }) => <ul className="mb-8 list-disc pl-7 space-y-3.5 marker:text-zinc-500 dark:marker:text-zinc-400">{children}</ul>,
                  ol: ({ children }) => <ol className="mb-8 list-decimal pl-7 space-y-3.5 marker:text-zinc-500 dark:marker:text-zinc-400">{children}</ol>,
                  li: ({ children }) => (
                    <li className="font-serif text-[1.1rem] leading-[1.86] text-[#242424] dark:text-zinc-200">
                      {children}
                    </li>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="mb-8 border-l-2 border-zinc-400 pl-5 font-serif text-[1.14rem] italic leading-[1.9] text-zinc-700 dark:border-zinc-600 dark:text-zinc-300">
                      {children}
                    </blockquote>
                  ),
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline decoration-zinc-400 underline-offset-4 transition-colors hover:text-zinc-900 dark:decoration-zinc-600 dark:hover:text-zinc-50"
                    >
                      {children}
                    </a>
                  ),
                  code: ({ className, children }) => {
                    const inline = !className;
                    return (
                      <code
                        className={cn(
                          inline
                            ? 'rounded bg-zinc-100 px-1.5 py-0.5 text-[0.91em] text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100'
                            : 'text-zinc-100'
                        )}
                      >
                        {children}
                      </code>
                    );
                  },
                  pre: ({ children }) => (
                    <pre className="mb-8 overflow-x-auto rounded-xl border border-zinc-200/80 bg-zinc-950 px-5 py-4 text-[0.88rem] leading-relaxed text-zinc-100 dark:border-zinc-700">
                      {children}
                    </pre>
                  ),
                }}
              >
                {normalized}
              </ReactMarkdown>
            </div>
          ) : (
            <ArticleRenderer text={normalized} />
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-zinc-300/80 bg-zinc-50/70 py-24 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900/30 dark:text-zinc-300">
          <p className="text-sm">原文内容暂不可用</p>
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm underline underline-offset-4 hover:text-zinc-900 dark:hover:text-zinc-50"
          >
            前往原始链接阅读 →
          </a>
        </div>
      )}
    </article>
  );
}
