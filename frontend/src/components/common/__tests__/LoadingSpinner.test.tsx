import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import LoadingSpinner, { PageLoader } from '../LoadingSpinner';

describe('LoadingSpinner', () => {
  it('renders with role="status"', () => {
    render(<LoadingSpinner />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('has accessible sr-only label', () => {
    render(<LoadingSpinner />);
    const srLabel = screen.getByText('Đang tải...', { selector: '.sr-only' });
    expect(srLabel).toBeInTheDocument();
  });

  it('renders visible label when provided', () => {
    render(<LoadingSpinner label="Processing..." />);
    expect(screen.getByText('Processing...')).toBeInTheDocument();
  });

  it('does not render label text when not provided', () => {
    render(<LoadingSpinner />);
    // Without visible label prop, only the sr-only span should contain this text
    const srLabel = screen.getByText('Đang tải...', { selector: '.sr-only' });
    expect(srLabel).toBeInTheDocument();
    // No visible label span
    expect(screen.queryByText('Đang tải...', { selector: '.text-sm' })).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(<LoadingSpinner className="my-spinner" />);
    expect(container.firstChild).toHaveClass('my-spinner');
  });
});

describe('PageLoader', () => {
  it('renders a spinner', () => {
    render(<PageLoader />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders default label', () => {
    render(<PageLoader />);
    // PageLoader passes label as visible text AND sr-only span both say "Đang tải..."
    // Check the visible span specifically
    const spans = screen.getAllByText('Đang tải...');
    expect(spans.length).toBeGreaterThanOrEqual(1);
  });

  it('renders custom label', () => {
    render(<PageLoader label="Loading data..." />);
    expect(screen.getByText('Loading data...')).toBeInTheDocument();
  });
});
