import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GapAnalysisPanel } from '../GapAnalysisPanel';
import type { KGGapSuggestion } from '@/lib/types';

const mockGaps: KGGapSuggestion[] = [
    {
        concept: 'Ring Attention',
        mastery: 0.1,
        adjacent_mastered: ['Attention Mechanism', 'Transformer'],
        reason: '与已掌握概念 Attention Mechanism, Transformer 相邻',
    },
    {
        concept: 'Flash Attention',
        mastery: 0.2,
        adjacent_mastered: ['Attention Mechanism'],
        reason: '与已掌握概念 Attention Mechanism 相邻',
    },
];

describe('GapAnalysisPanel', () => {
    const onConceptClick = vi.fn();

    it('renders panel with title', () => {
        render(<GapAnalysisPanel gaps={mockGaps} totalGaps={2} onConceptClick={onConceptClick} />);
        expect(screen.getByText('推荐学习')).toBeDefined();
    });

    it('shows gap count', () => {
        render(<GapAnalysisPanel gaps={mockGaps} totalGaps={2} onConceptClick={onConceptClick} />);
        expect(screen.getByText('2 个知识缺口')).toBeDefined();
    });

    it('renders gap suggestions', () => {
        render(<GapAnalysisPanel gaps={mockGaps} totalGaps={2} onConceptClick={onConceptClick} />);
        expect(screen.getByText('Ring Attention')).toBeDefined();
        expect(screen.getByText('Flash Attention')).toBeDefined();
    });

    it('shows mastery percentage for each gap', () => {
        render(<GapAnalysisPanel gaps={mockGaps} totalGaps={2} onConceptClick={onConceptClick} />);
        expect(screen.getByText('10%')).toBeDefined();
        expect(screen.getByText('20%')).toBeDefined();
    });

    it('shows adjacent mastered concepts', () => {
        render(<GapAnalysisPanel gaps={mockGaps} totalGaps={2} onConceptClick={onConceptClick} />);
        const badges = screen.getAllByText(/✓ Attention Mechanism/);
        expect(badges.length).toBeGreaterThanOrEqual(1);
    });

    it('calls onConceptClick when a gap is clicked', () => {
        render(<GapAnalysisPanel gaps={mockGaps} totalGaps={2} onConceptClick={onConceptClick} />);
        fireEvent.click(screen.getByText('Ring Attention'));
        expect(onConceptClick).toHaveBeenCalledWith('Ring Attention');
    });

    it('shows empty state when no gaps', () => {
        render(<GapAnalysisPanel gaps={[]} totalGaps={0} onConceptClick={onConceptClick} />);
        expect(screen.getByText(/暂无推荐/)).toBeDefined();
    });
});
