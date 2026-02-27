import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { OriginalContent } from '../OriginalContent';

describe('OriginalContent', () => {
  it('renders markdown content with heading', () => {
    render(
      <OriginalContent
        content={'# Desktop Extensions\n\nThis is a markdown paragraph.'}
        sourceUrl="https://example.com/article"
      />
    );

    expect(screen.getByText('Desktop Extensions')).toBeInTheDocument();
    expect(screen.getByText('This is a markdown paragraph.')).toBeInTheDocument();
  });

  it('normalizes html content into readable text', () => {
    render(
      <OriginalContent
        content={'<p>Alpha <strong>Beta</strong></p><p>Gamma</p>'}
        sourceUrl="https://example.com/article"
      />
    );

    expect(screen.getByText(/Alpha Beta/)).toBeInTheDocument();
    expect(screen.getByText('Gamma')).toBeInTheDocument();
  });

  it('shows fallback when original content is unavailable', () => {
    render(<OriginalContent content={null} sourceUrl="https://example.com/article" />);

    expect(screen.getByText('原文内容暂不可用')).toBeInTheDocument();
    expect(screen.getByText('前往原始链接阅读 →')).toBeInTheDocument();
  });
});
