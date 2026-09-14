import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { inventoryService } from '../services/inventoryService';
import type { InventoryUpdateRequest } from '../types/inventory';

export function useInventory(
  params?: { skip?: number; limit?: number; supply_id?: number; location?: string },
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['inventory', params],
    queryFn: () => inventoryService.getInventory(params),
    enabled: options?.enabled ?? true,
  });
}

export function useUpdateInventory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: InventoryUpdateRequest }) =>
      inventoryService.updateInventory(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['inventory'] }),
  });
}
