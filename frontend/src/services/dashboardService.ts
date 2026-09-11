import api from './api';
import type { DashboardCriticalAlert } from '../types/dashboard';
import type { DashboardForecast, DashboardV2, DashboardV2Params } from '../types/dashboardV2';

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
  /** Toàn bộ màn hình Tổng quan (Tuần 3). Nhanh — không khớp mô hình. */
  async getV2(params: DashboardV2Params): Promise<DashboardV2> {
    const response = await api.get<DashboardV2>('/dashboard/v2', {
      params: {
        focus: params.focus,
        ...(params.level ? { level: params.level } : {}),
        limit: params.limit ?? 8,
      },
    });
    return response.data;
  },

  /** Ŷ_g ba khối + khoảng. Lần đầu có thể mất vài chục giây (SARIMAX). */
  async getV2Forecast(force = false): Promise<DashboardForecast> {
    const response = await api.get<DashboardForecast>('/dashboard/v2/forecast', {
      params: force ? { force: true } : {},
      timeout: 180000,
    });
    return response.data;
  },

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
