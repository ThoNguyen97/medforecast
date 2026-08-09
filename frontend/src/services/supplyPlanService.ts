import api from './api';

export interface SupplyPlanItem {
  supply_code: string;
  name: string;
  unit: string;
  group_name: string;
  lead_time_days: number;
  demand_forecast: number;
  safety_level: number;
  current_stock: number;
  suggested_import: number;
  status: 'shortage' | 'sufficient';
}

export interface SupplyPlan {
  block: string;
  target_period: string;
  method: string;
  weather_used: boolean;
  group_forecast: number;
  group_interval: { lower: number; upper: number } | null;
  n_supplies: number;
  n_shortage: number;
  items: SupplyPlanItem[];
}

export const supplyPlanService = {
  async plan(block: string, method = 'top_down_dynamic'): Promise<SupplyPlan> {
    const r = await api.get<SupplyPlan>(`/supply-plan/${encodeURIComponent(block)}`, {
      params: { method },
    });
    return r.data;
  },
};
