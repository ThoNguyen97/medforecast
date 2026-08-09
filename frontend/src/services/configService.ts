import api from './api';
import type {
  SystemConfig,
  ConversionRatio,
  ShortageThreshold,
  ConfigUpdateRequest,
  ConversionRatiosUpdateRequest,
  ThresholdsUpdateRequest,
  AuditLog,
} from '../types/config';

export const configService = {
  /**
   * Get all system configurations
   */
  async getConfigs(): Promise<SystemConfig[]> {
    const response = await api.get<SystemConfig[]>('/config/');
    return response.data;
  },

  /**
   * Get a single configuration by key
   */
  async getConfigByKey(key: string): Promise<SystemConfig> {
    const response = await api.get<SystemConfig>(`/config/${key}`);
    return response.data;
  },

  /**
   * Update a configuration value by key (Admin only)
   */
  async updateConfig(key: string, data: ConfigUpdateRequest): Promise<SystemConfig> {
    const response = await api.put<SystemConfig>(`/config/${key}`, data);
    return response.data;
  },

  /**
   * Get all conversion ratios
   */
  async getConversionRatios(): Promise<ConversionRatio[]> {
    const response = await api.get<ConversionRatio[]>('/config/conversion-ratios');
    return response.data;
  },

  /**
   * Update conversion ratios (Admin only)
   */
  async updateConversionRatios(data: ConversionRatiosUpdateRequest): Promise<ConversionRatio[]> {
    const response = await api.put<ConversionRatio[]>('/config/conversion-ratios', data);
    return response.data;
  },

  /**
   * Get shortage thresholds (global)
   */
  async getThresholds(): Promise<ShortageThreshold> {
    const response = await api.get<ShortageThreshold>('/config/thresholds');
    return response.data;
  },

  /**
   * Update shortage thresholds (Admin only)
   */
  async updateThresholds(data: ThresholdsUpdateRequest): Promise<ShortageThreshold> {
    const response = await api.put<ShortageThreshold>('/config/thresholds', data);
    return response.data;
  },

  /**
   * Get audit logs for config change history (Admin only)
   * Backend trả về paginated object AuditLogListResponse {total, page, page_size, items}.
   * Frontend gọi với param `limit` để giữ tương thích ngược → map sang `page_size`.
   */
  async getAuditLogs(params?: {
    skip?: number;
    limit?: number;
    table_name?: string;
    action?: string;
    user_id?: number;
    start_date?: string;
    end_date?: string;
  }): Promise<AuditLog[]> {
    // Map skip/limit → page/page_size
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
    // Loại bỏ undefined để không gửi key rỗng
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
