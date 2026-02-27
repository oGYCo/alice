import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ModeIndicator } from '../ModeIndicator';
import type { ModeInfo } from '@/lib/types';

describe('ModeIndicator', () => {
    it('renders daily mode', () => {
        const data: ModeInfo = {
            current_mode: 'daily',
            recent_history: [{ mode: 'daily', timestamp: null }],
        };
        render(<ModeIndicator data={data} />);
        expect(screen.getByText('当前模式')).toBeDefined();
        expect(screen.getByText('日常模式')).toBeDefined();
    });

    it('renders mode-indicator class', () => {
        const data: ModeInfo = {
            current_mode: 'daily',
            recent_history: [{ mode: 'daily', timestamp: null }],
        };
        const { container } = render(<ModeIndicator data={data} />);
        expect(container.querySelector('.mode-indicator')).toBeDefined();
    });

    it('renders project mode', () => {
        const data: ModeInfo = {
            current_mode: 'project',
            recent_history: [{ mode: 'project', timestamp: null }],
        };
        render(<ModeIndicator data={data} />);
        expect(screen.getByText('专注模式')).toBeDefined();
    });

    it('renders explore mode', () => {
        const data: ModeInfo = {
            current_mode: 'explore',
            recent_history: [{ mode: 'explore', timestamp: null }],
        };
        render(<ModeIndicator data={data} />);
        expect(screen.getByText('探索模式')).toBeDefined();
    });

    it('renders low_energy mode', () => {
        const data: ModeInfo = {
            current_mode: 'low_energy',
            recent_history: [{ mode: 'low_energy', timestamp: null }],
        };
        render(<ModeIndicator data={data} />);
        expect(screen.getByText('低能耗模式')).toBeDefined();
    });

    it('shows recent history when more than 1 entry', () => {
        const data: ModeInfo = {
            current_mode: 'project',
            recent_history: [
                { mode: 'project', timestamp: '2026-02-27T10:00:00Z' },
                { mode: 'daily', timestamp: '2026-02-26T08:00:00Z' },
            ],
        };
        render(<ModeIndicator data={data} />);
        expect(screen.getByText('最近切换')).toBeDefined();
    });

    it('does not show history section when only 1 entry', () => {
        const data: ModeInfo = {
            current_mode: 'daily',
            recent_history: [{ mode: 'daily', timestamp: null }],
        };
        render(<ModeIndicator data={data} />);
        expect(screen.queryByText('最近切换')).toBeNull();
    });
});
