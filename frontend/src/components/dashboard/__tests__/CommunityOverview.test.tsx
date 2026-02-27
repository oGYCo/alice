import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CommunityOverview } from '../CommunityOverview';
import type { CommunityInfo } from '@/lib/types';

describe('CommunityOverview', () => {
    const sampleData: CommunityInfo[] = [
        {
            community_id: 0,
            label: 'Machine Learning',
            concept_count: 15,
            avg_mastery: 0.65,
            top_concepts: ['neural network', 'gradient descent', 'backpropagation'],
        },
        {
            community_id: 1,
            label: 'Distributed Systems',
            concept_count: 8,
            avg_mastery: 0.42,
            top_concepts: ['consensus', 'replication', 'sharding'],
        },
    ];

    it('renders with title', () => {
        render(<CommunityOverview data={sampleData} />);
        expect(screen.getByText('知识社区')).toBeDefined();
    });

    it('renders community-overview class', () => {
        const { container } = render(<CommunityOverview data={sampleData} />);
        expect(container.querySelector('.community-overview')).toBeDefined();
    });

    it('shows community labels', () => {
        render(<CommunityOverview data={sampleData} />);
        expect(screen.getByText('Machine Learning')).toBeDefined();
        expect(screen.getByText('Distributed Systems')).toBeDefined();
    });

    it('shows concept counts and mastery percentages', () => {
        render(<CommunityOverview data={sampleData} />);
        expect(screen.getByText(/15 概念/)).toBeDefined();
        expect(screen.getByText(/65% 掌握/)).toBeDefined();
    });

    it('shows top concepts as tags', () => {
        render(<CommunityOverview data={sampleData} />);
        expect(screen.getByText('neural network')).toBeDefined();
        expect(screen.getByText('consensus')).toBeDefined();
    });

    it('shows empty state when no communities', () => {
        render(<CommunityOverview data={[]} />);
        expect(screen.getByText(/暂无社区数据/)).toBeDefined();
    });

    it('renders community-cluster elements', () => {
        const { container } = render(<CommunityOverview data={sampleData} />);
        expect(container.querySelectorAll('.community-cluster').length).toBe(2);
    });
});
