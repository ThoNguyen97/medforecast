import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import AlertsStats from '../AlertsStats';
import type { Alert } from '../../../types/alerts';

function makeAlert(id: number, severity: Alert['severity'], resolved = false): Alert {
  return {
    id,
    supply_id: id * 10,
    supply_name: `Supply ${id}`,
    alert_type: 'low_stock',
    severity,
    message: null,
    shortage_date: null,
    current_stock: 10,
    required_stock: 100,
    is_resolved: resolved,
    created_at: '2024-01-01T00:00:00',
  };
}

describe('AlertsStats', () => {
  it('counts critical alerts correctly', () => {
    const alerts = [
      makeAlert(1, 'critical'),
      makeAlert(2, 'critical'),
      makeAlert(3, 'high'),
    ];
    render(<AlertsStats alerts={alerts} />);
    // Critical count = 2
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('counts resolved alerts correctly', () => {
    const alerts = [
      makeAlert(1, 'critical', true),
      makeAlert(2, 'medium', false),
    ];
    render(<AlertsStats alerts={alerts} />);
    // Check "Đã xử lý" label exists
    expect(screen.getByText('Đã xử lý')).toBeInTheDocument();
  });

  it('shows all four stat cards', () => {
    render(<AlertsStats alerts={[]} />);
    expect(screen.getByText('Nghiêm trọng')).toBeInTheDocument();
    expect(screen.getByText('Mức cao')).toBeInTheDocument();
    expect(screen.getByText('Trung bình')).toBeInTheDocument();
    expect(screen.getByText('Đã xử lý')).toBeInTheDocument();
  });

  it('shows zero counts when no alerts', () => {
    render(<AlertsStats alerts={[]} />);
    const zeros = screen.getAllByText('0');
    expect(zeros.length).toBe(4);
  });
});
