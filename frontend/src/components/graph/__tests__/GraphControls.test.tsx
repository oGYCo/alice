import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GraphControls, type GraphFilters } from '../GraphControls';
import type { KGCommunity } from '@/lib/types';

const mockCommunities: KGCommunity[] = [
    { community_id: 0, label: 'ML Core', concept_count: 12, avg_mastery: 0.75, concepts: [] },
    { community_id: 1, label: 'Systems', concept_count: 6, avg_mastery: 0.4, concepts: [] },
];

const defaultFilters: GraphFilters = {
    communityId: null,
    masteryRange: [0, 1],
    conceptType: null,
    searchQuery: '',
};

describe('GraphControls', () => {
    const onFiltersChange = vi.fn();
    const onLayoutChange = vi.fn();
    const onHeatmapToggle = vi.fn();
    const onFitView = vi.fn();
    const onSearch = vi.fn();

    const renderControls = (overrides: Partial<Parameters<typeof GraphControls>[0]> = {}) =>
        render(
            <GraphControls
                communities={mockCommunities}
                filters={defaultFilters}
                onFiltersChange={onFiltersChange}
                layout="force"
                onLayoutChange={onLayoutChange}
                heatmapMode={false}
                onHeatmapToggle={onHeatmapToggle}
                onFitView={onFitView}
                onSearch={onSearch}
                {...overrides}
            />,
        );

    it('renders search input', () => {
        renderControls();
        expect(screen.getByTestId('graph-search')).toBeDefined();
    });

    it('renders fit view button', () => {
        renderControls();
        expect(screen.getByTestId('fit-view-btn')).toBeDefined();
    });

    it('calls onFitView when fit button is clicked', () => {
        renderControls();
        fireEvent.click(screen.getByTestId('fit-view-btn'));
        expect(onFitView).toHaveBeenCalledTimes(1);
    });

    it('renders heatmap toggle button', () => {
        renderControls();
        expect(screen.getByTestId('heatmap-toggle')).toBeDefined();
    });

    it('calls onHeatmapToggle when heatmap button is clicked', () => {
        renderControls();
        fireEvent.click(screen.getByTestId('heatmap-toggle'));
        expect(onHeatmapToggle).toHaveBeenCalledTimes(1);
    });

    it('renders layout buttons', () => {
        renderControls();
        expect(screen.getByTestId('layout-force')).toBeDefined();
        expect(screen.getByTestId('layout-hierarchical')).toBeDefined();
        expect(screen.getByTestId('layout-radial')).toBeDefined();
    });

    it('calls onLayoutChange when layout button is clicked', () => {
        renderControls();
        fireEvent.click(screen.getByTestId('layout-hierarchical'));
        expect(onLayoutChange).toHaveBeenCalledWith('hierarchical');
    });

    it('shows filter panel when filter toggle is clicked', () => {
        renderControls();
        expect(screen.queryByTestId('filter-panel')).toBeNull();
        fireEvent.click(screen.getByTestId('filter-toggle'));
        expect(screen.getByTestId('filter-panel')).toBeDefined();
    });

    it('renders community filter options with correct labels', () => {
        renderControls();
        fireEvent.click(screen.getByTestId('filter-toggle'));
        const select = screen.getByTestId('community-filter') as HTMLSelectElement;
        expect(select.options.length).toBe(3); // empty + 2 communities
        expect(select.options[1].textContent).toContain('ML Core');
        expect(select.options[2].textContent).toContain('Systems');
    });

    it('calls onFiltersChange on search input', () => {
        renderControls();
        fireEvent.change(screen.getByTestId('graph-search'), { target: { value: 'attention' } });
        expect(onFiltersChange).toHaveBeenCalledWith(
            expect.objectContaining({ searchQuery: 'attention' }),
        );
        expect(onSearch).toHaveBeenCalledWith('attention');
    });

    it('renders type filter with all concept types', () => {
        renderControls();
        fireEvent.click(screen.getByTestId('filter-toggle'));
        const select = screen.getByTestId('type-filter') as HTMLSelectElement;
        expect(select.options.length).toBe(5); // empty + 4 types
    });
});
