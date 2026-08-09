import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import {
  useConfigs,
  useConfigByKey,
  useConversionRatios,
  useThresholds,
  useAuditLogs,
  useUpdateConfig,
  useUpdateConversionRatios,
  useUpdateThresholds,
} from '../useConfig';
import { configService } from '../../services/configService';

vi.mock('../../services/configService');

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useConfigs', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches all configs', async () => {
    vi.mocked(configService.getConfigs).mockResolvedValueOnce([]);
    const { result } = renderHook(() => useConfigs(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });
});

describe('useConfigByKey', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches config by key', async () => {
    const cfg = { config_key: 'threshold', config_value: '10' };
    vi.mocked(configService.getConfigByKey).mockResolvedValueOnce(cfg as any);
    const { result } = renderHook(() => useConfigByKey('threshold'), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(cfg);
  });

  it('does not fetch when key is empty', () => {
    const { result } = renderHook(() => useConfigByKey(''), { wrapper: makeWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });
});

describe('useConversionRatios', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches conversion ratios', async () => {
    vi.mocked(configService.getConversionRatios).mockResolvedValueOnce([]);
    const { result } = renderHook(() => useConversionRatios(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useThresholds', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches thresholds', async () => {
    vi.mocked(configService.getThresholds).mockResolvedValueOnce([]);
    const { result } = renderHook(() => useThresholds(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useAuditLogs', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches audit logs', async () => {
    vi.mocked(configService.getAuditLogs).mockResolvedValueOnce([]);
    const { result } = renderHook(() => useAuditLogs(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useUpdateConfig', () => {
  beforeEach(() => vi.clearAllMocks());

  it('calls updateConfig service', async () => {
    vi.mocked(configService.updateConfig).mockResolvedValueOnce({} as any);
    const { result } = renderHook(() => useUpdateConfig(), { wrapper: makeWrapper() });

    await act(async () => {
      await result.current.mutateAsync({ key: 'threshold', data: { config_value: '20' } });
    });

    expect(configService.updateConfig).toHaveBeenCalledWith('threshold', { config_value: '20' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useUpdateConversionRatios', () => {
  beforeEach(() => vi.clearAllMocks());

  it('calls updateConversionRatios service', async () => {
    vi.mocked(configService.updateConversionRatios).mockResolvedValueOnce([] as any);
    const { result } = renderHook(() => useUpdateConversionRatios(), { wrapper: makeWrapper() });

    await act(async () => {
      await result.current.mutateAsync({ ratios: [] } as any);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useUpdateThresholds', () => {
  beforeEach(() => vi.clearAllMocks());

  it('calls updateThresholds service', async () => {
    vi.mocked(configService.updateThresholds).mockResolvedValueOnce([] as any);
    const { result } = renderHook(() => useUpdateThresholds(), { wrapper: makeWrapper() });

    await act(async () => {
      await result.current.mutateAsync({ thresholds: [] } as any);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
