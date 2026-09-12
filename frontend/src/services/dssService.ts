import api from './api';
import type { AlertsPayload, AlertsQuery, DssParams, DssParamsUpdate, NormsPayload } from '../types/dss';
import type { BlockCode } from '../types/dashboardV2';

/**
 * Một công thức, một bộ tham số (12/09/2026).
 * Cảnh báo thiếu hụt, tham số DSS và bảng tra định mức thực nghiệm đều đi qua đây.
 */
export const dssService = {
  /** Toàn bộ dòng cảnh báo — cùng chuỗi Tầng 1→2→3 với Tổng quan, phân trang server. */
  async getAlerts(p: AlertsQuery): Promise<AlertsPayload> {
    const r = await api.get<AlertsPayload>('/dashboard/v2/alerts', {
      params: {
        focus: p.focus,
        ...(p.level ? { level: p.level } : {}),
        ...(p.q ? { q: p.q } : {}),
        ...(p.danh_muc ? { danh_muc: p.danh_muc } : {}),
        limit: p.limit ?? 50,
        offset: p.offset ?? 0,
      },
    });
    return r.data;
  },

  async getParams(): Promise<DssParams> {
    const r = await api.get<DssParams>('/dss/params');
    return r.data;
  },

  async updateParams(body: DssParamsUpdate): Promise<DssParams> {
    const r = await api.put<DssParams>('/dss/params', body);
    return r.data;
  },

  async getNorms(block: BlockCode, q?: string, limit = 50, offset = 0): Promise<NormsPayload> {
    const r = await api.get<NormsPayload>('/dss/norms', {
      params: { block, ...(q ? { q } : {}), limit, offset },
    });
    return r.data;
  },
};
