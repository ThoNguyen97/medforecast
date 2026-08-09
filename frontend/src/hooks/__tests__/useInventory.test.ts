import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import {
  useInventory,
  useInventoryById,
  useUpdateInventory,
  useLowStockItems,
  useExpiringItems,
} from '../useInventory';
import { inventoryService } from '../../services/inventoryService';
import type { Inventory } from '../../types/inventory';

vi.mock('../../services/inventoryService');

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

const mockInventory: Inventory = {
  id: 1,
  supply_id: 10,
  supply: {
    id: 10,
    name: 'Khẩu trang',
    category: 'mask',
    unit: 'cái',
    unit_price: 2000,
    minimum_order_quantity: 100,
    lead_time_days: 3,
    is_active: true,
    created_at: '2024-01-01T00:00:00',
    updated_at: '2024-01-01T00:00:00',
  },
  quantity_on_hand: 500,
  safety_stock_level: 100,
  reorder_point: 150,
  storage_capacity: 10000,
  last_updated: '2024-01-01T00:00:00',
  stock_status: 'safe',
};

describe('useInventory', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches inventory list', async () => {
    vi.mocked(inventoryService.getInventory).mockResolvedValueOnce([mockInventory]);
    const { result } = renderHook(() => useInventory(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([mockInventory]);
  });

  it('handles fetch error', async () => {
    vi.mocked(inventoryService.getInventory).mockRejectedValueOnce(new Error('Failed'));
    const { result } = renderHook(() => useInventory(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useInventoryById', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches single inventory item', async () => {
    vi.mocked(inventoryService.getInventoryById).mockResolvedValueOnce(mockInventory);
    const { result } = renderHook(() => useInventoryById(1), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockInventory);
  });

  it('skips fetch when id is 0 (falsy)', () => {
    const { result } = renderHook(() => useInventoryById(0), { wrapper: makeWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });
});

describe('useUpdateInventory', () => {
  beforeEach(() => vi.clearAllMocks());

  it('calls updateInventory service and succeeds', async () => {
    const updated = { ...mockInventory, quantity_on_hand: 700 };
    vi.mocked(inventoryService.updateInventory).mockResolvedValueOnce(updated);
    const { result } = renderHook(() => useUpdateInventory(), { wrapper: makeWrapper() });

    await act(async () => {
      await result.current.mutateAsync({ id: 1, data: { quantity_on_hand: 700 } });
    });

    expect(inventoryService.updateInventory).toHaveBeenCalledWith(1, { quantity_on_hand: 700 });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useLowStockItems', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches low stock items', async () => {
    vi.mocked(inventoryService.getLowStockItems).mockResolvedValueOnce([mockInventory]);
    const { result } = renderHook(() => useLowStockItems(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([mockInventory]);
  });
});

describe('useExpiringItems', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches expiring items', async () => {
    vi.mocked(inventoryService.getExpiringItems).mockResolvedValueOnce([]);
    const { result } = renderHook(() => useExpiringItems(30), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });
});
