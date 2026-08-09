import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import {
  useDiseaseCases,
  useCreateDiseaseCase,
  useDiseaseStatistics,
  useDiseaseTrends,
} from '../useEpidemiology';
import { epidemiologyService } from '../../services/epidemiologyService';

vi.mock('../../services/epidemiologyService');

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useDiseaseCases', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches disease cases', async () => {
    vi.mocked(epidemiologyService.getDiseaseCases).mockResolvedValueOnce([]);
    const { result } = renderHook(() => useDiseaseCases(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });

  it('handles error', async () => {
    vi.mocked(epidemiologyService.getDiseaseCases).mockRejectedValueOnce(new Error('err'));
    const { result } = renderHook(() => useDiseaseCases(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useCreateDiseaseCase', () => {
  beforeEach(() => vi.clearAllMocks());

  it('calls createDiseaseCase service', async () => {
    const newCase = { id: 1, disease_type: 'dengue_fever' };
    vi.mocked(epidemiologyService.createDiseaseCase).mockResolvedValueOnce(newCase as any);
    const { result } = renderHook(() => useCreateDiseaseCase(), { wrapper: makeWrapper() });

    await act(async () => {
      await result.current.mutateAsync({
        disease_type: 'dengue_fever',
        case_count: 5,
        location: 'HCM',
        recorded_at: '2024-01-01T00:00:00',
      } as any);
    });

    expect(epidemiologyService.createDiseaseCase).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useDiseaseStatistics', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches disease statistics', async () => {
    const stats = { dengue_fever: 100 };
    vi.mocked(epidemiologyService.getStatistics).mockResolvedValueOnce(stats as any);
    const { result } = renderHook(() => useDiseaseStatistics(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(stats);
  });
});

describe('useDiseaseTrends', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches disease trends', async () => {
    vi.mocked(epidemiologyService.getTrends).mockResolvedValueOnce({ trends: [] } as any);
    const { result } = renderHook(
      () => useDiseaseTrends({ disease_type: 'dengue_fever' }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
