import api from './api';
import type { DashboardV2, DashboardV2Params } from '../types/dashboardV2';

/** API trang Tổng quan (/dashboard/v2). */
export const dashboardService = {
  /** Toàn bộ dữ liệu trang Tổng quan; không khớp mô hình nên phản hồi nhanh. */
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
};
