import api from './api';
import type { DashboardCriticalAlert } from '../types/dashboard';

export interface DashboardSummary {
  total_cases_current: number;
  cases_trend_pct: number;
  predicted_cases_next_month: number;
  predicted_trend_pct: number;
  shortage_supplies_count: number;
  overall_risk: 'Thấp' | 'Trung bình' | 'Cao';
  as_of: string;
}

export interface CaseTrendPoint {
  month: string;
  value: number;
}

export interface CaseTrendResponse {
  this_year: CaseTrendPoint[];
  last_year: CaseTrendPoint[];
}

export interface DemandVsStockItem {
  supply_id: number;
  supply_name: string;
  unit: string;
  demand: number;
  stock: number;
}

export const dashboardService = {
  async getSummary(): Promise<DashboardSummary> {
    const response = await api.get<DashboardSummary>('/dashboard/summary');
    return response.data;
  },

  async getCaseTrend(months = 6): Promise<CaseTrendResponse> {
    const response = await api.get<CaseTrendResponse>('/dashboard/case-trend', {
      params: { months },
    });
    return response.data;
  },

  async getDemandVsStock(topN = 5): Promise<DemandVsStockItem[]> {
    const response = await api.get<DemandVsStockItem[]>('/dashboard/demand-vs-stock', {
      params: { top_n: topN },
    });
    return response.data;
  },

  async getCriticalAlerts(limit = 5, refresh = false): Promise<DashboardCriticalAlert[]> {
    const response = await api.get<{ alerts: DashboardCriticalAlert[] }>(
      '/dashboard/critical-alerts',
      {
        params: { limit, ...(refresh ? { refresh: true } : {}) },
      },
    );
    // Backend trả về { alerts: [...], total_returned, severity_summary }
    return response.data?.alerts ?? [];
  },
};
