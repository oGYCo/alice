import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KnowledgeGrowth } from '../KnowledgeGrowth';
import type { KnowledgeGrowthPoint } from '@/lib/types';

vi.mock('recharts', async (importOriginal) => {
    const actual = await importOriginal<typeof import('recharts')>();
    return {
        ...actual,
        ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
            <div data-testid="responsive-container" style={{ width: 500, height: 300 }}>
                {children}
            </div>
        ),
    };
});

describe('KnowledgeGrowth', () => {
    const sampleData: KnowledgeGrowthPoint[] = [
        { week: '2026-W05', total_nodes: 20, new_nodes: 5, mastered_nodes: 3 },
        { week: '2026-W06', total_nodes: 28, new_nodes: 8, mastered_nodes: 5 },
        { week: '2026-W07', total_nodes: 35, new_nodes: 7, mastered_nodes: 8 },
        { week: '2026-W08', total_nodes: 42, new_nodes: 7, mastered_nodes: 10 },
    ];

    it('renders with title', () => {
        render(<KnowledgeGrowth data={sampleData} />);
        expect(screen.getByText('知识增长')).toBeDefined();
    });

    it('renders knowledge-growth class', () => {
        const { container } = render(<KnowledgeGrowth data={sampleData} />);
        expect(container.querySelector('.knowledge-growth')).toBeDefined();
    });

    it('renders chart when data provided', () => {
        render(<KnowledgeGrowth data={sampleData} />);
        expect(screen.getByTestId('responsive-container')).toBeDefined();
    });

    it('shows empty state when no data', () => {
        render(<KnowledgeGrowth data={[]} />);
        expect(screen.getByText('暂无数据')).toBeDefined();
    });
});
