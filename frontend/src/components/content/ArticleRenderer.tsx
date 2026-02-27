import React from 'react';

type Block =
    | { type: 'heading'; text: string }
    | { type: 'paragraph'; text: string }
    | { type: 'list'; items: string[] }
    | { type: 'code'; text: string };

const MAX_HEADING_LEN = 68;
const MAX_HEADING_WORDS = 10;
const SENTENCE_END = /[.!?:,;。！？：；…]$/;
const LIST_BULLET = /^[-•*]\s+/;
const LIST_ORDERED = /^\d+[.)]\s+/;
const CJK_CHAR = /[\u3400-\u9fff]/;
const CODE_FENCE = /^```/;

function parseBlocks(text: string): Block[] {
    const normalized = text.replace(/\r\n?/g, '\n').trim();
    if (!normalized) return [];

    const lines = normalized.split('\n');
    const blocks: Block[] = [];
    let i = 0;

    while (i < lines.length) {
        const rawLine = lines[i];
        const line = rawLine.trim();

        // Skip empty lines
        if (!line) {
            i++;
            continue;
        }

        // Markdown code fence
        if (CODE_FENCE.test(line)) {
            const codeLines: string[] = [];
            i++;
            while (i < lines.length && !CODE_FENCE.test(lines[i].trim())) {
                codeLines.push(lines[i]);
                i++;
            }
            if (i < lines.length) i++;
            blocks.push({ type: 'code', text: codeLines.join('\n').trim() });
            continue;
        }

        // List block
        if (LIST_BULLET.test(line) || LIST_ORDERED.test(line)) {
            const items: string[] = [];
            while (i < lines.length) {
                const current = lines[i].trim();
                if (!current) break;
                if (!LIST_BULLET.test(current) && !LIST_ORDERED.test(current)) break;
                items.push(current.replace(LIST_BULLET, '').replace(LIST_ORDERED, '').trim());
                i++;
            }
            blocks.push({ type: 'list', items });
            continue;
        }

        // ATX-style markdown heading
        if (/^#{1,6}\s+/.test(line)) {
            blocks.push({ type: 'heading', text: line.replace(/^#{1,6}\s+/, '').trim() });
            i++;
            continue;
        }

        // Candidate chunk until blank line
        const chunk: string[] = [];
        while (i < lines.length && lines[i].trim()) {
            chunk.push(lines[i].trim());
            i++;
        }

        if (chunk.length === 1) {
            const maybeHeading = chunk[0];
            if (isLikelyHeading(maybeHeading)) {
                blocks.push({ type: 'heading', text: maybeHeading });
                continue;
            }
        }

        blocks.push({ type: 'paragraph', text: chunk.join(' ') });
    }

    return blocks;
}

function isLikelyHeading(text: string): boolean {
    const trimmed = text.trim();
    if (!trimmed) return false;
    if (trimmed.length > MAX_HEADING_LEN) return false;
    if (SENTENCE_END.test(trimmed)) return false;
    if (LIST_BULLET.test(trimmed) || LIST_ORDERED.test(trimmed)) return false;
    if (/^https?:\/\//i.test(trimmed)) return false;

    if (CJK_CHAR.test(trimmed)) {
        return trimmed.length <= 26;
    }

    const words = trimmed.split(/\s+/).filter(Boolean);
    if (words.length === 0 || words.length > MAX_HEADING_WORDS) return false;
    if (!/^[A-Z0-9"'\(\[]/.test(trimmed)) return false;
    if (/[a-z]/.test(trimmed.slice(0, 1))) return false;

    return true;
}

interface ArticleRendererProps {
    text: string;
}

export function ArticleRenderer({ text }: ArticleRendererProps) {
    const blocks = React.useMemo(() => parseBlocks(text), [text]);

    return (
        <div className="space-y-0 text-[#1f1f1f] dark:text-zinc-100">
            {blocks.map((block, idx) => {
                switch (block.type) {
                    case 'heading':
                        return (
                            <h2
                                key={idx}
                                className="mt-14 mb-5 font-serif text-[2rem] leading-[1.16] tracking-[-0.014em] text-[#111111] first:mt-0 dark:text-zinc-50"
                            >
                                {block.text}
                            </h2>
                        );
                    case 'paragraph':
                        return (
                            <p
                                key={idx}
                                className="mb-8 font-serif text-[1.17rem] leading-[1.92] tracking-[0.002em] text-[#232323] dark:text-zinc-200"
                            >
                                {block.text}
                            </p>
                        );
                    case 'list':
                        return (
                            <ul key={idx} className="mb-8 space-y-3.5">
                                {block.items.map((item, j) => (
                                    <li
                                        key={j}
                                        className="flex gap-3.5 font-serif text-[1.1rem] leading-[1.86] text-[#242424] dark:text-zinc-200"
                                    >
                                        <span className="mt-[0.76em] h-1.5 w-1.5 rounded-full bg-[#7f7f7f] dark:bg-zinc-400" />
                                        <span>{item}</span>
                                    </li>
                                ))}
                            </ul>
                        );
                    case 'code':
                        return (
                            <pre
                                key={idx}
                                className="mb-8 overflow-x-auto rounded-xl border border-zinc-200/80 bg-zinc-950 px-5 py-4 text-[0.88rem] leading-relaxed text-zinc-100 dark:border-zinc-700"
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
