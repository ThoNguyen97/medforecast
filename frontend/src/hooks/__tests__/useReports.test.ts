import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import {
  useConsumptionReport,
  useForecastAccuracyReport,
  useInventoryTurnoverReport,
} from '../useReports';
import { reportsService } from '../../services/reportsService';

vi.mock('../../services/reportsService');

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useConsumptionReport', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches consumption report', async () => {
    const data = { categories: [], total_consumed: 100 };
    vi.mocked(reportsService.getConsumptionReport).mockResolvedValueOnce(data as any);
    const { result } = renderHook(() => useConsumptionReport(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(data);
  });

  it('handles errors', async () => {
    vi.mocked(reportsService.getConsumptionReport).mockRejectedValueOnce(new Error('err'));
    const { result } = renderHook(() => useConsumptionReport(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useForecastAccuracyReport', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches forecast accuracy report', async () => {
    vi.mocked(reportsService.getForecastAccuracyReport).mockResolvedValueOnce({} as any);
    const { result } = renderHook(() => useForecastAccuracyReport(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useInventoryTurnoverReport', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches inventory turnover report', async () => {
    vi.mocked(reportsService.getInventoryTurnoverReport).mockResolvedValueOnce({} as any);
    const { result } = renderHook(() => useInventoryTurnoverReport(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
