import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AlertFilters from '../AlertFilters';

const defaultProps = {
  selectedSeverity: 'all' as const,
  selectedDateRange: '30',
  showResolved: false,
  onSeverityChange: vi.fn(),
  onDateRangeChange: vi.fn(),
  onShowResolvedChange: vi.fn(),
};

describe('AlertFilters', () => {
  it('renders severity select', () => {
    render(<AlertFilters {...defaultProps} />);
    expect(screen.getByLabelText(/mức độ/i)).toBeInTheDocument();
  });

  it('renders date range buttons', () => {
    render(<AlertFilters {...defaultProps} />);
    expect(screen.getByRole('button', { name: '7 ngày' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '30 ngày' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '90 ngày' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tất cả' })).toBeInTheDocument();
  });

  it('renders show resolved toggle', () => {
    render(<AlertFilters {...defaultProps} />);
    expect(screen.getByText('Hiển thị đã xử lý')).toBeInTheDocument();
  });

  it('calls onSeverityChange when select changes', () => {
    const onSeverityChange = vi.fn();
    render(<AlertFilters {...defaultProps} onSeverityChange={onSeverityChange} />);
    fireEvent.change(screen.getByLabelText(/mức độ/i), { target: { value: 'critical' } });
    expect(onSeverityChange).toHaveBeenCalledWith('critical');
  });

  it('calls onDateRangeChange when date button clicked', () => {
    const onDateRangeChange = vi.fn();
    render(<AlertFilters {...defaultProps} onDateRangeChange={onDateRangeChange} />);
    fireEvent.click(screen.getByRole('button', { name: '7 ngày' }));
    expect(onDateRangeChange).toHaveBeenCalledWith('7');
  });

  it('calls onShowResolvedChange when toggle clicked', () => {
    const onShowResolvedChange = vi.fn();
    render(<AlertFilters {...defaultProps} onShowResolvedChange={onShowResolvedChange} />);
    // Click the toggle div directly
    const toggleDiv = document.querySelector('[class*="rounded-full"][class*="cursor-pointer"]')!;
    fireEvent.click(toggleDiv);
    expect(onShowResolvedChange).toHaveBeenCalledWith(true);
  });
});
