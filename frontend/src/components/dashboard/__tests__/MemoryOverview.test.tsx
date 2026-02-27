import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryOverview } from '../MemoryOverview';
import type { MemoryTierStats } from '@/lib/types';

describe('MemoryOverview', () => {
    const sampleData: MemoryTierStats = {
        working: 3,
        short_term: 12,
        long_term: 25,
    };

    it('renders with title', () => {
        render(<MemoryOverview data={sampleData} />);
        expect(screen.getByText('记忆层级')).toBeDefined();
    });

    it('renders memory-overview class', () => {
        const { container } = render(<MemoryOverview data={sampleData} />);
        expect(container.querySelector('.memory-overview')).toBeDefined();
    });

    it('displays all three memory tiers', () => {
        render(<MemoryOverview data={sampleData} />);
        expect(screen.getByText('工作记忆')).toBeDefined();
        expect(screen.getByText('短期记忆')).toBeDefined();
        expect(screen.getByText('长期记忆')).toBeDefined();
    });

    it('shows tier counts', () => {
        render(<MemoryOverview data={sampleData} />);
        expect(screen.getByText('3')).toBeDefined();
        expect(screen.getByText('12')).toBeDefined();
        expect(screen.getByText('25')).toBeDefined();
    });

    it('shows total count', () => {
        render(<MemoryOverview data={sampleData} />);
        expect(screen.getByText('总计 40 个记忆项')).toBeDefined();
    });

    it('has 3 memory-tier elements', () => {
        const { container } = render(<MemoryOverview data={sampleData} />);
        const tiers = container.querySelectorAll('.memory-tier');
        expect(tiers.length).toBe(3);
    });

    it('handles zero counts', () => {
        render(<MemoryOverview data={{ working: 0, short_term: 0, long_term: 0 }} />);
        expect(screen.getByText('总计 0 个记忆项')).toBeDefined();
    });
});
