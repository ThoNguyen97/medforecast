/**
 * Hợp đồng dữ liệu — /api/v1/inventory (backend app/schemas/base.py:
 * MedicalSupplyResponse, InventoryResponse, InventoryUpdate).
 *
 * Không có trường mua sắm (reorder_point, storage_capacity, MOQ, lead time):
 * hệ thống là DSS thuần, tồn kho chỉ mang tồn hiện có và ngưỡng tham khảo.
 */

export interface MedicalSupply {
  id: number;
  supply_code: string;
  drug_code: string;
  ten_hoat_chat: string;
  unit: string;
  group_name: string;
  category: string | null;
  unit_price: number | null;
  description: string | null;
  created_at: string;
}

export interface Inventory {
  id: number;
  supply_id: number;
  supply: MedicalSupply | null;
  current_stock: number;      // có thể âm — HIS xuất trước nhập bù sau
  safety_stock: number;       // ngưỡng tham khảo, không tham gia DOI
  location: string | null;
  batch_number: string | null;
  expiry_date: string | null;
  last_updated: string;
}

export interface InventoryUpdateRequest {
  current_stock?: number;
  safety_stock?: number;
  location?: string;
}
