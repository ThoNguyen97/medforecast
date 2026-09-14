import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import { useForecastAccuracyReport } from '../useReports';
import { reportsService } from '../../services/reportsService';

vi.mock('../../services/reportsService');

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useForecastAccuracyReport', () => {
  beforeEach(() => vi.clearAllMocks());

  it('gọi API khi enabled', async () => {
    vi.mocked(reportsService.getForecastAccuracyReport).mockResolvedValueOnce({} as any);
    const { result } = renderHook(() => useForecastAccuracyReport(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it('không gọi API khi enabled = false', async () => {
    const { result } = renderHook(
      () => useForecastAccuracyReport(undefined, { enabled: false }),
      { wrapper: makeWrapper() },
    );
    expect(result.current.fetchStatus).toBe('idle');
    expect(reportsService.getForecastAccuracyReport).not.toHaveBeenCalled();
  });

  it('trả lỗi khi API lỗi', async () => {
    vi.mocked(reportsService.getForecastAccuracyReport).mockRejectedValueOnce(new Error('err'));
    const { result } = renderHook(() => useForecastAccuracyReport(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
