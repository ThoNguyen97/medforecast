import api from './api';
import type {
  ForecastAccuracyReport,
  ExportReportRequest,
  ReportFilters,
} from '../types/reports';

/** /reports — xem trước độ chính xác dự báo và xuất PDF/Excel. */
export const reportsService = {
  /** GET /reports/forecast-accuracy — độ lệch dự báo/thực tế theo mô hình và theo tháng. */
  async getForecastAccuracyReport(filters?: ReportFilters): Promise<ForecastAccuracyReport> {
    const response = await api.get<ForecastAccuracyReport>('/reports/forecast-accuracy', {
      params: {
        start_date: filters?.start_date,
        end_date: filters?.end_date,
        disease_type: filters?.disease_type || undefined,
        model_used: filters?.model_used || undefined,
      },
    });
    return response.data;
  },

  /** POST /reports/export — sinh báo cáo PDF/Excel, trả Blob để bên gọi tải về. */
  async exportReport(payload: ExportReportRequest & { format?: 'pdf' | 'excel' }): Promise<Blob> {
    const response = await api.post('/reports/export', payload, {
      responseType: 'blob',
    });
    return response.data as Blob;
  },
};
