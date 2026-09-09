import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Alerts from '../Alerts';
import * as useAlertsHooks from '../../hooks/useAlerts';
import { alertsService } from '../../services/alertsService';
import type { Alert } from '../../types/alerts';

vi.mock('../../services/alertsService');

const makeAlert = (id: number, severity: Alert['severity'], resolved = false): Alert => ({
  id,
  supply_id: id * 10,
  supply_name: `Supply ${id}`,
  alert_type: 'low_stock',
  severity,
  message: `Message ${id}`,
  shortage_date: '2024-03-01',
  current_stock: 10,
  required_stock: 100,
  is_resolved: resolved,
  created_at: new Date().toISOString(),
});

function makeQueryResult<T>(data: T, overrides = {}) {
  return {
    data,
    isLoading: false,
    isError: false,
    isSuccess: true,
    refetch: vi.fn(),
    ...overrides,
  } as any;
}

function makeMutationResult(overrides = {}) {
  return {
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
    isSuccess: false,
    isError: false,
    ...overrides,
  } as any;
}

describe('Alerts page', () => {
  beforeEach(() => {
    vi.spyOn(useAlertsHooks, 'useAlerts').mockReturnValue(
      makeQueryResult([
        makeAlert(1, 'critical'),
        makeAlert(2, 'high'),
        makeAlert(3, 'medium', true),
      ])
    );
    vi.spyOn(useAlertsHooks, 'useResolveAlert').mockReturnValue(
      makeMutationResult()
    );
  });

  it('renders page heading', () => {
    render(<Alerts />);
    expect(screen.getByText('Cảnh báo Thiếu hụt')).toBeInTheDocument();
  });

  it('shows active alert count badge', () => {
    render(<Alerts />);
    // Badge showing active count is a rounded circle (check for a span with "2" inside alerts heading area)
    const allTwos = screen.getAllByText('2');
    expect(allTwos.length).toBeGreaterThanOrEqual(1);
  });

  it('shows alert stats', () => {
    render(<Alerts />);
    // AlertsStats renders "Nghiêm trọng" text - use getAllByText since it may appear multiple times
    const elements = screen.getAllByText('Nghiêm trọng');
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  it('shows loading state', () => {
    vi.spyOn(useAlertsHooks, 'useAlerts').mockReturnValue(
      makeQueryResult(undefined, { isLoading: true, data: undefined })
    );
    render(<Alerts />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders refresh button', () => {
    render(<Alerts />);
    expect(screen.getByRole('button', { name: /làm mới/i })).toBeInTheDocument();
  });

  it('opens confirm modal when resolve button clicked', async () => {
    render(<Alerts />);
    // Find a resolve button (there should be 2 for unresolved alerts)
    const resolveButtons = screen.getAllByRole('button', { name: /xử lý/i });
    fireEvent.click(resolveButtons[0]);
    // Confirm modal should appear
    await waitFor(() => {
      expect(screen.getByText('Xử lý cảnh báo')).toBeInTheDocument();
    });
  });
});
