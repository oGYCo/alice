/**
 * ArticleRenderer: smart plain-text → structured HTML.
 *
 * The extracted_text field from the pipeline is plain text with \n separators.
 * Short standalone lines are de-facto section headers; lines starting with "- "
 * or a number+dot are list items; everything else becomes paragraphs.
 */

import React from 'react';

type Block =
    | { type: 'heading'; text: string }
    | { type: 'paragraph'; text: string }
    | { type: 'list'; items: string[] }
    | { type: 'code'; text: string };

const MAX_HEADING_LEN = 80;
const SENTENCE_END = /[.!?:,;。！？…]$/;
const LIST_BULLET = /^[-•*]\s+/;
const LIST_ORDERED = /^\d+[.)]\s+/;
const CODE_INDENT = /^\s{4}|\t/;

function isHeading(line: string): boolean {
    const trimmed = line.trim();
    if (!trimmed) return false;
    if (trimmed.length > MAX_HEADING_LEN) return false;
    if (SENTENCE_END.test(trimmed)) return false;
    if (LIST_BULLET.test(trimmed) || LIST_ORDERED.test(trimmed)) return false;
    // Must look like a section title: no lowercase start with context OR all-caps words
    return true;
}

function parseBlocks(text: string): Block[] {
    const lines = text.split('\n').map((l) => l.trimEnd());
    const blocks: Block[] = [];
    let i = 0;

    while (i < lines.length) {
        const line = lines[i];

        // Skip empty lines
        if (!line.trim()) {
            i++;
            continue;
        }

        // Code block (4+ spaces or tab indent)
        if (CODE_INDENT.test(line)) {
            const codeLines: string[] = [];
            while (i < lines.length && (CODE_INDENT.test(lines[i]) || !lines[i].trim())) {
                codeLines.push(lines[i]);
                i++;
            }
            blocks.push({ type: 'code', text: codeLines.join('\n').trimEnd() });
            continue;
        }

        // List block
        if (LIST_BULLET.test(line) || LIST_ORDERED.test(line)) {
            const items: string[] = [];
            while (i < lines.length && (LIST_BULLET.test(lines[i]) || LIST_ORDERED.test(lines[i]))) {
                items.push(lines[i].replace(LIST_BULLET, '').replace(LIST_ORDERED, '').trim());
                i++;
            }
            blocks.push({ type: 'list', items });
            continue;
        }

        // Heading heuristic: short line, not ending in sentence punctuation,
        // followed by empty line OR another different-looking line
        const nextLine = lines[i + 1] ?? '';
        if (isHeading(line) && (!nextLine.trim() || isHeading(nextLine) || nextLine.length > MAX_HEADING_LEN)) {
            blocks.push({ type: 'heading', text: line.trim() });
            i++;
            continue;
        }

        // Paragraph: accumulate consecutive non-special lines
        const paraLines: string[] = [];
        while (
            i < lines.length &&
            lines[i].trim() &&
            !CODE_INDENT.test(lines[i]) &&
            !LIST_BULLET.test(lines[i]) &&
            !LIST_ORDERED.test(lines[i])
        ) {
            const curr = lines[i].trim();
            const next = (lines[i + 1] ?? '').trim();
            paraLines.push(curr);
            i++;
            // Break paragraph if next line looks like a heading
            if (next && isHeading(next) && (!lines[i + 1] || !lines[i + 1].trim())) break;
        }
        if (paraLines.length) {
            blocks.push({ type: 'paragraph', text: paraLines.join(' ') });
        }
    }

    return blocks;
}

interface ArticleRendererProps {
    text: string;
}

export function ArticleRenderer({ text }: ArticleRendererProps) {
    const blocks = React.useMemo(() => parseBlocks(text), [text]);

    return (
        <div className="article-body">
            {blocks.map((block, idx) => {
                switch (block.type) {
                    case 'heading':
                        return (
                            <h2
                                key={idx}
                                className="text-[22px] font-bold tracking-tight text-foreground mt-12 mb-4 first:mt-0"
                            >
                                {block.text}
                            </h2>
                        );
                    case 'paragraph':
                        return (
                            <p key={idx} className="text-[17px] leading-[1.85] text-foreground/85 mb-6">
                                {block.text}
                            </p>
                        );
                    case 'list':
                        return (
                            <ul key={idx} className="mb-6 space-y-3 pl-1">
                                {block.items.map((item, j) => (
                                    <li
                                        key={j}
                                        className="flex gap-3 text-[17px] leading-[1.75] text-foreground/85"
                                    >
                                        <span className="mt-[9px] flex-shrink-0 w-1.5 h-1.5 rounded-full bg-foreground/40" />
                                        <span>{item}</span>
                                    </li>
                                ))}
                            </ul>
                        );
                    case 'code':
                        return (
                            <pre
                                key={idx}
                                className="overflow-x-auto rounded-lg bg-muted px-5 py-4 text-[13.5px] font-mono leading-relaxed text-foreground mb-6 border border-border/40"
                            >
                                <code>{block.text}</code>
                            </pre>
                        );
                    default:
                        return null;
                }
            })}
        </div>
    );
}
