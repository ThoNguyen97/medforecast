import api from './api';
import type { SystemConfig, ConfigUpdateRequest, AuditLog } from '../types/config';

// Ngưỡng cảnh báo DSS (`dss.thresholds`) đọc qua dssService, không qua đây

export const configService = {
  /** Toàn bộ cấu hình hệ thống. */
  async getConfigs(): Promise<SystemConfig[]> {
    const response = await api.get<SystemConfig[]>('/config/');
    return response.data;
  },

  /** Một cấu hình theo khoá. */
  async getConfigByKey(key: string): Promise<SystemConfig> {
    const response = await api.get<SystemConfig>(`/config/${key}`);
    return response.data;
  },

  /** Cập nhật giá trị cấu hình theo khoá (chỉ Quản trị viên). */
  async updateConfig(key: string, data: ConfigUpdateRequest): Promise<SystemConfig> {
    const response = await api.put<SystemConfig>(`/config/${key}`, data);
    return response.data;
  },

  /** Nhật ký thay đổi cấu hình (chỉ Quản trị viên); skip/limit quy đổi sang page/page_size. */
  async getAuditLogs(params?: {
    skip?: number;
    limit?: number;
    table_name?: string;
    action?: string;
    user_id?: number;
    start_date?: string;
    end_date?: string;
  }): Promise<AuditLog[]> {
    const page_size = Math.min(params?.limit ?? 50, 200);
    const page = params?.skip ? Math.floor(params.skip / page_size) + 1 : 1;
    const queryParams: Record<string, unknown> = {
      page,
      page_size,
      table_name: params?.table_name,
      action: params?.action,
      user_id: params?.user_id,
      start_date: params?.start_date,
      end_date: params?.end_date,
    };
    Object.keys(queryParams).forEach(
      (k) => queryParams[k] === undefined && delete queryParams[k],
    );
    const response = await api.get<{
      total: number;
      page: number;
      page_size: number;
      items: AuditLog[];
    }>('/audit-logs', { params: queryParams });
    return response.data?.items ?? [];
  },
};
