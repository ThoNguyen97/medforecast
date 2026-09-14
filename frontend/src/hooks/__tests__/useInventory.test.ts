import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import { useInventory } from '../useInventory';
import { inventoryService } from '../../services/inventoryService';

vi.mock('../../services/inventoryService');

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useInventory', () => {
  beforeEach(() => vi.clearAllMocks());

  it('tải danh sách tồn kho', async () => {
    vi.mocked(inventoryService.getInventory).mockResolvedValueOnce([{ id: 1 }] as any);
    const { result } = renderHook(() => useInventory({ limit: 10 }), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
  });

  it('không gọi API khi enabled = false', () => {
    const { result } = renderHook(() => useInventory(undefined, { enabled: false }), {
      wrapper: makeWrapper(),
    });
    expect(result.current.fetchStatus).toBe('idle');
    expect(inventoryService.getInventory).not.toHaveBeenCalled();
  });
});
