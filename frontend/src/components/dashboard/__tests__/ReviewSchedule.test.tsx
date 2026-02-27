import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReviewSchedule } from '../ReviewSchedule';
import type { ReviewScheduleStats } from '@/lib/types';

describe('ReviewSchedule', () => {
    const sampleData: ReviewScheduleStats = {
        due_today: 5,
        due_this_week: 18,
        total_cards: 42,
        streak_days: 7,
        cards_by_state: {
            new: 10,
            learning: 8,
            review: 20,
            relearning: 4,
        },
    };

    it('renders with title', () => {
        render(<ReviewSchedule data={sampleData} />);
        expect(screen.getByText('复习计划')).toBeDefined();
    });

    it('renders review-schedule class', () => {
        const { container } = render(<ReviewSchedule data={sampleData} />);
        expect(container.querySelector('.review-schedule')).toBeDefined();
    });

    it('shows due today count', () => {
        render(<ReviewSchedule data={sampleData} />);
        expect(screen.getByText('5')).toBeDefined();
        expect(screen.getByText('今日待复习')).toBeDefined();
    });

    it('shows due this week count', () => {
        render(<ReviewSchedule data={sampleData} />);
        expect(screen.getByText('18')).toBeDefined();
        expect(screen.getByText('本周待复习')).toBeDefined();
    });

    it('shows total cards', () => {
        render(<ReviewSchedule data={sampleData} />);
        expect(screen.getByText('42')).toBeDefined();
    });

    it('shows streak days', () => {
        render(<ReviewSchedule data={sampleData} />);
        expect(screen.getByText('7')).toBeDefined();
        expect(screen.getByText('连续天数')).toBeDefined();
    });

    it('shows cards by state distribution', () => {
        render(<ReviewSchedule data={sampleData} />);
        expect(screen.getByText('新卡片')).toBeDefined();
        expect(screen.getByText('学习中')).toBeDefined();
        expect(screen.getByText('复习中')).toBeDefined();
        expect(screen.getByText('重新学习')).toBeDefined();
    });

    it('handles empty cards_by_state', () => {
        const emptyState = { ...sampleData, cards_by_state: {} };
        const { container } = render(<ReviewSchedule data={emptyState} />);
        // Should not render the state distribution section
        expect(screen.queryByText('卡片状态分布')).toBeNull();
        // But should still render the main stats
        expect(container.querySelector('.review-schedule')).toBeDefined();
    });
});
