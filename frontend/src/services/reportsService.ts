import api from './api';
import type {
  ConsumptionReport,
  ForecastAccuracyReport,
  InventoryTurnoverReport,
  ExportReportRequest,
  ReportFilters,
} from '../types/reports';

/**
 * Reports service — wraps all /reports API endpoints.
 */
export const reportsService = {
  /**
   * GET /reports/consumption
   * Returns aggregated supply usage broken down by category.
   */
  async getConsumptionReport(filters?: ReportFilters): Promise<ConsumptionReport> {
    const response = await api.get<ConsumptionReport>('/reports/consumption', {
      params: {
        start_date: filters?.start_date,
        end_date: filters?.end_date,
        location: filters?.location || undefined,
        category: filters?.category || undefined,
      },
    });
    return response.data;
  },

  /**
   * GET /reports/forecast-accuracy
   * Returns model accuracy metrics over time.
   */
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

  /**
   * GET /reports/inventory-turnover
   * Returns inventory turnover rates per supply.
   */
  async getInventoryTurnoverReport(filters?: ReportFilters): Promise<InventoryTurnoverReport> {
    const response = await api.get<InventoryTurnoverReport>('/reports/inventory-turnover', {
      params: {
        start_date: filters?.start_date,
        end_date: filters?.end_date,
        location: filters?.location || undefined,
        category: filters?.category || undefined,
      },
    });
    return response.data;
  },

  /**
   * POST /reports/export
   * Generates and downloads a PDF or Excel report.
   * Returns a Blob so the caller can trigger a file download.
   */
  async exportReport(payload: ExportReportRequest & { format?: 'pdf' | 'excel' }): Promise<Blob> {
    const response = await api.post('/reports/export', payload, {
      responseType: 'blob',
    });
    return response.data as Blob;
  },
};
