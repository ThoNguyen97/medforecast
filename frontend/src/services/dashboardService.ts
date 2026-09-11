import api from './api';
import type { DashboardForecast, DashboardV2, DashboardV2Params } from '../types/dashboardV2';

/**
 * Dashboard v2 (Tuần 3). Bốn endpoint cũ (summary / case-trend /
 * demand-vs-stock / critical-alerts) không còn màn hình nào gọi — gỡ khỏi
 * service 11/09/2026; backend vẫn giữ summary/case-trend/critical-alerts
 * (chỉ đọc), demand-vs-stock đã xoá cùng topdown.py.
 */
export const dashboardService = {
  /** Toàn bộ màn hình Tổng quan. Nhanh — không khớp mô hình. */
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
};
