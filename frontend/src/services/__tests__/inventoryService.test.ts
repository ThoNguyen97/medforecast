import { describe, it, expect, vi, beforeEach } from 'vitest';
import { inventoryService } from '../inventoryService';
import api from '../api';
import type { Inventory } from '../../types/inventory';

vi.mock('../api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

const makeInventory = (id: number): Inventory => ({
  id,
  supply_id: id * 10,
  supply: {
    id: id * 10,
    name: `Supply ${id}`,
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
});

describe('inventoryService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getInventory', () => {
    it('calls GET /inventory and returns items', async () => {
      const items = [makeInventory(1), makeInventory(2)];
      vi.mocked(api.get).mockResolvedValueOnce({ data: items });

      const result = await inventoryService.getInventory();
      expect(api.get).toHaveBeenCalledWith('/inventory', { params: undefined });
      expect(result).toEqual(items);
    });

    it('passes query params', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
      await inventoryService.getInventory({ limit: 10, skip: 0 });
      expect(api.get).toHaveBeenCalledWith('/inventory', { params: { limit: 10, skip: 0 } });
    });
  });

  describe('getInventoryById', () => {
    it('calls GET /inventory/:id', async () => {
      const item = makeInventory(5);
      vi.mocked(api.get).mockResolvedValueOnce({ data: item });
      const result = await inventoryService.getInventoryById(5);
      expect(api.get).toHaveBeenCalledWith('/inventory/5');
      expect(result).toEqual(item);
    });
  });

  describe('updateInventory', () => {
    it('calls PUT /inventory/:id with data', async () => {
      const updated = makeInventory(1);
      vi.mocked(api.put).mockResolvedValueOnce({ data: updated });
      const result = await inventoryService.updateInventory(1, { quantity_on_hand: 600 });
      expect(api.put).toHaveBeenCalledWith('/inventory/1', { quantity_on_hand: 600 });
      expect(result).toEqual(updated);
    });
  });

  describe('getLowStockItems', () => {
    it('calls GET /inventory/low-stock', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
      await inventoryService.getLowStockItems();
      expect(api.get).toHaveBeenCalledWith('/inventory/low-stock', { params: { threshold: undefined } });
    });

    it('passes threshold param', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
      await inventoryService.getLowStockItems(50);
      expect(api.get).toHaveBeenCalledWith('/inventory/low-stock', { params: { threshold: 50 } });
    });
  });

  describe('getExpiringItems', () => {
    it('calls GET /inventory/expiring', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
      await inventoryService.getExpiringItems(30);
      expect(api.get).toHaveBeenCalledWith('/inventory/expiring', { params: { days: 30 } });
    });
  });

  describe('batchUpdateInventory', () => {
    it('calls POST /inventory/batch-update', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({ data: [] });
      const updates = [{ inventory_id: 1, current_stock: 100 }];
      await inventoryService.batchUpdateInventory(updates);
      expect(api.post).toHaveBeenCalledWith('/inventory/batch-update', updates);
    });
  });
});
