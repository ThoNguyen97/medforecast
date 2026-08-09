import type { StockStatus } from './inventory';

export interface DashboardOverview {
  total_supplies: number;
  total_inventory_value: number;
  high_risk_shortages: number;
  predicted_demand_30d: number;
  disease_outbreaks: number;
  supply_risk_percentage: number;
  safe_stock_items: number;
  low_stock_items: number;
  critical_risk_items: number;
}

export interface SupplyDemandPoint {
  date: string;
  actual: number | null;
  forecast: number | null;
}

export interface SupplyDemandPayload {
  supply_id: number | null;
  days_history: number;
  days_forecast: number;
  data_points: SupplyDemandPoint[];
  total_historical_points: number;
  total_forecast_points: number;
}

export interface RiskStatusData {
  total_items: number;
  safe_count: number;
  low_count: number;
  critical_count: number;
  safe_percentage: number;
  low_percentage: number;
  critical_percentage: number;
}

export type AlertSeverity = 'critical' | 'high' | 'medium';

export interface DashboardCriticalAlert {
  id: number;
  supply_name: string;
  severity: AlertSeverity;
  shortage_date: string | null;
  current_stock: number | null;
  required_stock: number | null;
  message: string | null;
}

export interface Alert {
  id: number;
  supply_id: number;
  supply_name: string;
  supply_category: string;
  severity: AlertSeverity;
  message: string;
  projected_shortage_date: string;
  shortage_quantity: number;
  current_stock: number;
  required_quantity: number;
  is_resolved: boolean;
  resolved_at?: string;
  resolved_by?: string;
  created_at: string;
  updated_at: string;
}

export interface StockStatusItem {
  supply_id: number;
  supply_name: string;
  category: string;
  stock_status: StockStatus;
  quantity_on_hand: number;
  safety_stock_level: number;
}
