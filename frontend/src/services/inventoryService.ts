import api from './api';
import type { Inventory, InventoryUpdateRequest } from '../types/inventory';

export const inventoryService = {
  /**
   * Get all inventory items with optional filters
   */
  async getInventory(params?: {
    skip?: number;
    limit?: number;
    supply_id?: number;
    location?: string;
  }): Promise<Inventory[]> {
    const response = await api.get<Inventory[]>('/inventory/', { params });
    return response.data;
  },

  /**
   * Get a single inventory item by ID
   */
  async getInventoryById(id: number): Promise<Inventory> {
    const response = await api.get<Inventory>(`/inventory/${id}`);
    return response.data;
  },

  /**
   * Update inventory stock levels
   */
  async updateInventory(
    id: number,
    data: InventoryUpdateRequest
  ): Promise<Inventory> {
    const response = await api.put<Inventory>(`/inventory/${id}`, data);
    return response.data;
  },

  /**
   * Get low stock items
   */
  async getLowStockItems(threshold?: number): Promise<Inventory[]> {
    const response = await api.get<Inventory[]>('/inventory/low-stock', {
      params: { threshold },
    });
    return response.data;
  },

  /**
   * Get expiring items
   */
  async getExpiringItems(days?: number): Promise<Inventory[]> {
    const response = await api.get<Inventory[]>('/inventory/expiring', {
      params: { days },
    });
    return response.data;
  },

  /**
   * Batch update multiple inventory items
   */
  async batchUpdateInventory(
    updates: Array<{ inventory_id: number; current_stock?: number; safety_stock?: number }>
  ): Promise<Inventory[]> {
    const response = await api.post<Inventory[]>('/inventory/batch-update', updates);
    return response.data;
  },
};
