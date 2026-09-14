import { describe, it, expect, vi, beforeEach } from 'vitest';
import { inventoryService } from '../inventoryService';
import api from '../api';

vi.mock('../api', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));

describe('inventoryService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getInventory gọi GET /inventory/ kèm params', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
    await inventoryService.getInventory({ limit: 50 });
    expect(api.get).toHaveBeenCalledWith('/inventory/', { params: { limit: 50 } });
  });

  it('updateInventory gọi PUT /inventory/{id}', async () => {
    vi.mocked(api.put).mockResolvedValueOnce({ data: { id: 3 } });
    await inventoryService.updateInventory(3, { current_stock: 10 });
    expect(api.put).toHaveBeenCalledWith('/inventory/3', { current_stock: 10 });
  });
});
