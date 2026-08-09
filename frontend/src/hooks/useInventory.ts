import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { inventoryService } from '../services/inventoryService';
import type { InventoryUpdateRequest } from '../types/inventory';

export function useInventory(params?: {
  skip?: number;
  limit?: number;
  supply_id?: number;
  location?: string;
}) {
  return useQuery({
    queryKey: ['inventory', params],
    queryFn: () => inventoryService.getInventory(params),
  });
}

export function useInventoryById(id: number) {
  return useQuery({
    queryKey: ['inventory', id],
    queryFn: () => inventoryService.getInventoryById(id),
    enabled: !!id,
  });
}

export function useUpdateInventory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: InventoryUpdateRequest }) =>
      inventoryService.updateInventory(id, data),
    onSuccess: () => {
      // Invalidate and refetch inventory queries
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
    },
  });
}

export function useLowStockItems(threshold?: number) {
  return useQuery({
    queryKey: ['inventory', 'low-stock', threshold],
    queryFn: () => inventoryService.getLowStockItems(threshold),
  });
}

export function useExpiringItems(days?: number) {
  return useQuery({
    queryKey: ['inventory', 'expiring', days],
    queryFn: () => inventoryService.getExpiringItems(days),
  });
}

export function useBatchUpdateInventory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (
      updates: Array<{ inventory_id: number; current_stock?: number; safety_stock?: number }>
    ) => inventoryService.batchUpdateInventory(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
    },
  });
}
