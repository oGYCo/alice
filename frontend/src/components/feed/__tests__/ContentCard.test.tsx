import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ContentCard } from '../ContentCard';
import { ContentItem } from '@/lib/types';
import React from 'react';

// Mock next/link
vi.mock('next/link', () => ({ 
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> 
}));

const mockItem: ContentItem = {
  id: 1,
  title: 'Test Content Title',
  url: 'https://example.com',
  summary: 'This is a test summary for the content card.',
  source: 'TechCrunch',
  source_url: 'https://techcrunch.com',
  content_type: 'knowledge',
  quality_score: 8,
  p_score: 0.9,
  pipeline_status: 'processed',
  created_at: new Date().toISOString(),
  published_at: null,
  pushed_at: null,
  metadata_: null,
};

const defaultProps = {
  onDelete: () => {},
  isSelectMode: false,
  isSelected: false,
  onToggleSelect: () => {},
};

describe('ContentCard', () => {
  it('renders without crash', () => {
    render(<ContentCard item={mockItem} onFeedback={() => {}} viewMode="grid" {...defaultProps} />);
    expect(screen.getByTestId('content-card')).toBeInTheDocument();
  });

  it('shows title and summary', () => {
    render(<ContentCard item={mockItem} onFeedback={() => {}} viewMode="grid" {...defaultProps} />);
    expect(screen.getByText('Test Content Title')).toBeInTheDocument();
    expect(screen.getByText('This is a test summary for the content card.')).toBeInTheDocument();
  });

  it('shows content_type badge with correct label', () => {
    render(<ContentCard item={mockItem} onFeedback={() => {}} viewMode="grid" {...defaultProps} />);
    expect(screen.getByText('硬核知识')).toBeInTheDocument();
  });

  it('shows all feedback buttons', () => {
    render(<ContentCard item={mockItem} onFeedback={() => {}} viewMode="grid" {...defaultProps} />);
    // In grid mode, buttons have titles
    expect(screen.getByTitle('高质量')).toBeInTheDocument();
    expect(screen.getByTitle('稍后再看')).toBeInTheDocument();
    expect(screen.getByTitle('已知晓')).toBeInTheDocument();
    expect(screen.getByTitle('无价值')).toBeInTheDocument();
  });

  it('clicking like button calls onFeedback with correct args', () => {
    const handleFeedback = vi.fn();
    render(<ContentCard item={mockItem} onFeedback={handleFeedback} viewMode="grid" {...defaultProps} />);
    
    fireEvent.click(screen.getByTitle('高质量'));
    expect(handleFeedback).toHaveBeenCalledWith(1, 'positive');
  });

  it('renders different layout classes for grid vs list', () => {
    const { rerender } = render(<ContentCard item={mockItem} onFeedback={() => {}} viewMode="grid" {...defaultProps} />);
    const card = screen.getByTestId('content-card');
    expect(card.className).toContain('flex-col');
    
    rerender(<ContentCard item={mockItem} onFeedback={() => {}} viewMode="list" {...defaultProps} />);
    const updatedCard = screen.getByTestId('content-card');
    expect(updatedCard.className).toContain('flex-row');
  });
});
