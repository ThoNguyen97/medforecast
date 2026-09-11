import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import {
  useAlerts,
  useActiveAlerts,
  useAlertById,
  useCriticalAlerts,
  useResolveAlert,
} from '../useAlerts';
import { alertsService } from '../../services/alertsService';
import type { Alert } from '../../types/alerts';

vi.mock('../../services/alertsService');

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

const mockAlert: Alert = {
  id: 1,
  supply_id: 10,
  supply_name: 'Khẩu trang',
  alert_type: 'low_stock',
  severity: 'critical',
  message: 'Low stock critical',
  shortage_date: '2024-02-01',
  current_stock: 50,
  required_stock: 300,
  is_resolved: false,
  created_at: '2024-01-01T00:00:00',
};

describe('useAlerts', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches alerts list', async () => {
    vi.mocked(alertsService.getAlerts).mockResolvedValueOnce([mockAlert]);
    const { result } = renderHook(() => useAlerts(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([mockAlert]);
  });

  it('handles fetch error', async () => {
    vi.mocked(alertsService.getAlerts).mockRejectedValueOnce(new Error('Server error'));
    const { result } = renderHook(() => useAlerts(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useActiveAlerts', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches active alerts', async () => {
    vi.mocked(alertsService.getActiveAlerts).mockResolvedValueOnce([mockAlert]);
    const { result } = renderHook(() => useActiveAlerts(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
  });
});

describe('useAlertById', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches alert by id', async () => {
    vi.mocked(alertsService.getAlertById).mockResolvedValueOnce(mockAlert);
    const { result } = renderHook(() => useAlertById(1), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockAlert);
  });

  it('does not fetch when id is falsy (0)', () => {
    const { result } = renderHook(() => useAlertById(0), { wrapper: makeWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });
});

describe('useCriticalAlerts', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches critical alerts', async () => {
    vi.mocked(alertsService.getCriticalAlerts).mockResolvedValueOnce([mockAlert]);
    const { result } = renderHook(() => useCriticalAlerts(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([mockAlert]);
  });
});

describe('useResolveAlert', () => {
  beforeEach(() => vi.clearAllMocks());

  it('calls resolveAlert service', async () => {
    const resolved = { ...mockAlert, is_resolved: true };
    vi.mocked(alertsService.resolveAlert).mockResolvedValueOnce(resolved);
    const { result } = renderHook(() => useResolveAlert(), { wrapper: makeWrapper() });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    expect(alertsService.resolveAlert).toHaveBeenCalledWith(1);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
