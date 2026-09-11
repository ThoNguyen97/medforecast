import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AlertsList from '../AlertsList';
import type { Alert } from '../../../types/alerts';

const makeAlert = (id: number, severity: Alert['severity'], resolved = false): Alert => ({
  id,
  supply_id: id * 10,
  supply_name: `Supply ${id}`,
  alert_type: 'low_stock',
  severity,
  message: `Alert ${id}`,
  shortage_date: null,
  current_stock: 10,
  required_stock: 100,
  is_resolved: resolved,
  created_at: '2024-01-01T00:00:00',
});

describe('AlertsList', () => {
  it('shows loading spinner when isLoading=true', () => {
    render(<AlertsList alerts={[]} isLoading resolvingId={null} onResolve={vi.fn()} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows empty state when no alerts', () => {
    render(<AlertsList alerts={[]} resolvingId={null} onResolve={vi.fn()} />);
    expect(screen.getByText(/không có cảnh báo/i)).toBeInTheDocument();
  });

  it('renders alert cards', () => {
    const alerts = [makeAlert(1, 'critical'), makeAlert(2, 'high')];
    render(<AlertsList alerts={alerts} resolvingId={null} onResolve={vi.fn()} />);
    expect(screen.getByText('Supply 1')).toBeInTheDocument();
    expect(screen.getByText('Supply 2')).toBeInTheDocument();
  });

  it('sorts critical alerts before high alerts', () => {
    const alerts = [makeAlert(1, 'high'), makeAlert(2, 'critical')];
    render(<AlertsList alerts={alerts} resolvingId={null} onResolve={vi.fn()} />);
    const items = screen.getAllByText(/Supply \d/);
    // Supply 2 (critical) should appear first in sorted output
    expect(items[0].textContent).toBe('Supply 2');
    expect(items[1].textContent).toBe('Supply 1');
  });

  it('sorts unresolved before resolved', () => {
    const alerts = [
      makeAlert(1, 'medium', true),  // resolved
      makeAlert(2, 'medium', false), // unresolved
    ];
    render(<AlertsList alerts={alerts} resolvingId={null} onResolve={vi.fn()} />);
    const items = screen.getAllByText(/Supply \d/);
    expect(items[0].textContent).toBe('Supply 2'); // unresolved first
    expect(items[1].textContent).toBe('Supply 1'); // resolved last
  });
});
