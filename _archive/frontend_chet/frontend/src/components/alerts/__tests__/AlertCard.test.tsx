import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AlertCard from '../AlertCard';
import type { Alert } from '../../../types/alerts';

const makeAlert = (overrides?: Partial<Alert>): Alert => ({
  id: 1,
  supply_id: 10,
  supply_name: 'Khẩu trang y tế',
  alert_type: 'low_stock',
  severity: 'critical',
  message: 'Tồn kho thấp nghiêm trọng',
  shortage_date: '2024-02-15',
  current_stock: 50,
  required_stock: 300,
  is_resolved: false,
  created_at: '2024-01-15T10:00:00',
  ...overrides,
});

describe('AlertCard', () => {
  it('renders supply name', () => {
    render(<AlertCard alert={makeAlert()} onResolve={vi.fn()} />);
    expect(screen.getByText('Khẩu trang y tế')).toBeInTheDocument();
  });

  it('renders message', () => {
    render(<AlertCard alert={makeAlert()} onResolve={vi.fn()} />);
    expect(screen.getByText('Tồn kho thấp nghiêm trọng')).toBeInTheDocument();
  });

  it('shows severity badge for critical', () => {
    render(<AlertCard alert={makeAlert({ severity: 'critical' })} onResolve={vi.fn()} />);
    expect(screen.getByText('Nghiêm trọng')).toBeInTheDocument();
  });

  it('shows severity badge for high', () => {
    render(<AlertCard alert={makeAlert({ severity: 'high' })} onResolve={vi.fn()} />);
    expect(screen.getByText('Cao')).toBeInTheDocument();
  });

  it('shows severity badge for medium', () => {
    render(<AlertCard alert={makeAlert({ severity: 'medium' })} onResolve={vi.fn()} />);
    expect(screen.getByText('Trung bình')).toBeInTheDocument();
  });

  it('shows current stock', () => {
    render(<AlertCard alert={makeAlert({ current_stock: 50 })} onResolve={vi.fn()} />);
    expect(screen.getByText('50')).toBeInTheDocument();
  });

  it('shows required stock', () => {
    render(<AlertCard alert={makeAlert({ required_stock: 300 })} onResolve={vi.fn()} />);
    expect(screen.getByText('300')).toBeInTheDocument();
  });

  it('shows resolve button for unresolved alerts', () => {
    render(<AlertCard alert={makeAlert({ is_resolved: false })} onResolve={vi.fn()} />);
    expect(screen.getByRole('button', { name: /xử lý/i })).toBeInTheDocument();
  });

  it('does not show resolve button for resolved alerts', () => {
    render(<AlertCard alert={makeAlert({ is_resolved: true })} onResolve={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /xử lý/i })).not.toBeInTheDocument();
  });

  it('calls onResolve with alert id when resolve button clicked', () => {
    const onResolve = vi.fn();
    render(<AlertCard alert={makeAlert({ id: 5 })} onResolve={onResolve} />);
    fireEvent.click(screen.getByRole('button', { name: /xử lý/i }));
    expect(onResolve).toHaveBeenCalledWith(5);
  });

  it('shows critical alert banner', () => {
    render(<AlertCard alert={makeAlert({ severity: 'critical', is_resolved: false })} onResolve={vi.fn()} />);
    expect(screen.getByText(/Cảnh báo Nghiêm trọng/i)).toBeInTheDocument();
  });

  it('does not show critical banner when resolved', () => {
    render(<AlertCard alert={makeAlert({ severity: 'critical', is_resolved: true })} onResolve={vi.fn()} />);
    expect(screen.queryByText(/Cảnh báo Nghiêm trọng/i)).not.toBeInTheDocument();
  });

  it('shows "Đã xử lý" for resolved alerts', () => {
    render(<AlertCard alert={makeAlert({ is_resolved: true })} onResolve={vi.fn()} />);
    expect(screen.getByText('Đã xử lý')).toBeInTheDocument();
  });
});
