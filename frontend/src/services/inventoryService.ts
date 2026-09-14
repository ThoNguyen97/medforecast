import api from './api';
import type { Inventory, InventoryUpdateRequest } from '../types/inventory';

/** /api/v1/inventory — trang Quản lý thuốc gọi thẳng `api` cho import/CSV; đây là phần dùng chung. */
export const inventoryService = {
  async getInventory(params?: {
    skip?: number;
    limit?: number;
    supply_id?: number;
    location?: string;
  }): Promise<Inventory[]> {
    const response = await api.get<Inventory[]>('/inventory/', { params });
    return response.data;
  },

  async updateInventory(id: number, data: InventoryUpdateRequest): Promise<Inventory> {
    const response = await api.put<Inventory>(`/inventory/${id}`, data);
    return response.data;
  },
};
