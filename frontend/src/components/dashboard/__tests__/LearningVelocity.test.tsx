import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LearningVelocity } from '../LearningVelocity';
import type { WeeklyVelocity } from '@/lib/types';

// Mock recharts to avoid canvas issues in test environment
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

describe('LearningVelocity', () => {
    const sampleData: WeeklyVelocity[] = [
        { week: '2026-W01', count: 5 },
        { week: '2026-W02', count: 8 },
        { week: '2026-W03', count: 12 },
        { week: '2026-W04', count: 7 },
        { week: '2026-W05', count: 15 },
        { week: '2026-W06', count: 10 },
        { week: '2026-W07', count: 9 },
        { week: '2026-W08', count: 14 },
    ];

    it('renders with title', () => {
        render(<LearningVelocity data={sampleData} />);
        expect(screen.getByText('学习速度')).toBeDefined();
    });

    it('renders learning-velocity class', () => {
        const { container } = render(<LearningVelocity data={sampleData} />);
        expect(container.querySelector('.learning-velocity')).toBeDefined();
    });

    it('renders chart container when data is provided', () => {
        render(<LearningVelocity data={sampleData} />);
        expect(screen.getByTestId('responsive-container')).toBeDefined();
    });

    it('shows empty state when no data', () => {
        render(<LearningVelocity data={[]} />);
        expect(screen.getByText('暂无数据')).toBeDefined();
    });
});
