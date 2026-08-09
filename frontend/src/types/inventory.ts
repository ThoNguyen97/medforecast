export type SupplyCategory =
  | 'mask'
  | 'glove'
  | 'test_kit'
  | 'disinfectant'
  | 'medicine'
  | 'iv_fluid'
  | 'other';

export type StockStatus = 'safe' | 'low' | 'critical';

export interface MedicalSupply {
  id: number;
  name: string;
  category: SupplyCategory;
  unit: string;
  unit_price: number;
  minimum_order_quantity: number;
  lead_time_days: number;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Inventory {
  id: number;
  supply_id: number;
  supply: MedicalSupply;
  quantity_on_hand: number;
  safety_stock_level: number;
  reorder_point: number;
  storage_capacity: number;
  last_updated: string;
  stock_status: StockStatus;
  days_until_shortage?: number;
}

export interface InventoryUpdateRequest {
  quantity_on_hand: number;
  safety_stock_level?: number;
  reorder_point?: number;
}

export interface InventoryBatchUpdateItem {
  supply_id: number;
  quantity_on_hand: number;
}

export interface InventoryBatchUpdateRequest {
  items: InventoryBatchUpdateItem[];
}

export interface LowStockItem {
  inventory_id: number;
  supply_name: string;
  category: SupplyCategory;
  quantity_on_hand: number;
  safety_stock_level: number;
  shortage_amount: number;
  stock_status: StockStatus;
}

export interface ExpiringItem {
  inventory_id: number;
  supply_name: string;
  category: SupplyCategory;
  quantity: number;
  expiry_date: string;
  days_until_expiry: number;
}
