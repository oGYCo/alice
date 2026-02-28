import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NodeEditor } from '../NodeEditor';
import type { KGNode, KGEdge } from '@/lib/types';

const mockNode: KGNode = {
    id: 'Attention Mechanism',
    name: 'Attention Mechanism',
    label: 'Concept',
    mastery: 0.75,
    community_id: 0,
    aliases: ['attention', 'self-attention'],
};

const mockEdges: KGEdge[] = [
    { id: 'Attention Mechanism-PREREQUISITE_OF-Transformer', source: 'Attention Mechanism', target: 'Transformer', label: 'PREREQUISITE_OF' },
    { id: 'Information Theory-EXTENDS-Attention Mechanism', source: 'Information Theory', target: 'Attention Mechanism', label: 'EXTENDS' },
];

const mockAllNodes: KGNode[] = [
    mockNode,
    { id: 'Transformer', name: 'Transformer', label: 'Method', mastery: 0.6, community_id: 0, aliases: [] },
    { id: 'Information Theory', name: 'Information Theory', label: 'Theory', mastery: 0.4, community_id: 1, aliases: [] },
];

describe('NodeEditor', () => {
    const onClose = vi.fn();
    const onUpdateMastery = vi.fn();
    const onRenameNode = vi.fn();
    const onDeleteEdge = vi.fn();
    const onCreateEdge = vi.fn();

    const renderEditor = () =>
        render(
            <NodeEditor
                node={mockNode}
                edges={mockEdges}
                allNodes={mockAllNodes}
                onClose={onClose}
                onUpdateMastery={onUpdateMastery}
                onRenameNode={onRenameNode}
                onDeleteEdge={onDeleteEdge}
                onCreateEdge={onCreateEdge}
            />,
        );

    it('renders node editor panel', () => {
        renderEditor();
        expect(screen.getByTestId('node-editor')).toBeDefined();
    });

    it('displays concept name', () => {
        renderEditor();
        const nameInput = screen.getByTestId('node-name-input') as HTMLInputElement;
        expect(nameInput.value).toBe('Attention Mechanism');
    });

    it('displays concept type badge', () => {
        renderEditor();
        expect(screen.getByText(/Concept/)).toBeDefined();
    });

    it('displays aliases', () => {
        renderEditor();
        expect(screen.getByText('attention')).toBeDefined();
        expect(screen.getByText('self-attention')).toBeDefined();
    });

    it('renders mastery slider with correct value', () => {
        renderEditor();
        const slider = screen.getByTestId('mastery-slider') as HTMLInputElement;
        expect(slider.value).toBe('0.75');
    });

    it('shows connected edges', () => {
        renderEditor();
        expect(screen.getByText(/Transformer/)).toBeDefined();
        expect(screen.getByText(/Information Theory/)).toBeDefined();
    });

    it('shows edge count', () => {
        renderEditor();
        // The section label '关系' contains the count as child text
        const labels = screen.getAllByText('关系', { exact: false });
        const edgeLabel = labels.find((el) => el.textContent?.includes('(2)'));
        expect(edgeLabel).toBeDefined();
    });

    it('calls onClose when close button is clicked', () => {
        renderEditor();
        fireEvent.click(screen.getByTestId('close-editor'));
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onUpdateMastery when mastery is changed and saved', () => {
        renderEditor();
        const slider = screen.getByTestId('mastery-slider') as HTMLInputElement;
        fireEvent.change(slider, { target: { value: '0.9' } });
        fireEvent.click(screen.getByTestId('save-mastery'));
        expect(onUpdateMastery).toHaveBeenCalledWith('Attention Mechanism', 0.9);
    });

    it('renders new edge inputs', () => {
        renderEditor();
        expect(screen.getByTestId('new-edge-target')).toBeDefined();
        expect(screen.getByTestId('new-edge-relation')).toBeDefined();
        expect(screen.getByTestId('add-edge-btn')).toBeDefined();
    });

    it('calls onCreateEdge when new edge is submitted', () => {
        renderEditor();
        fireEvent.change(screen.getByTestId('new-edge-target'), { target: { value: 'New Concept' } });
        fireEvent.click(screen.getByTestId('add-edge-btn'));
        expect(onCreateEdge).toHaveBeenCalledWith('Attention Mechanism', 'New Concept', 'PREREQUISITE_OF');
    });

    it('disables add edge button when target is empty', () => {
        renderEditor();
        const addBtn = screen.getByTestId('add-edge-btn');
        expect(addBtn).toHaveProperty('disabled', true);
    });
});
