import { useQuery } from '@tanstack/react-query';
import { inventoryService } from '../services/inventoryService';

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

