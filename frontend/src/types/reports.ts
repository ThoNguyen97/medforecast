// Hợp đồng /reports/forecast-accuracy và POST /reports/export.

// Bộ lọc báo cáo

export interface ReportFilters {
  start_date?: string; // YYYY-MM-DD
  end_date?: string;   // YYYY-MM-DD
  location?: string;
  category?: string;
  disease_type?: string;
  model_used?: string;
}

// Báo cáo độ chính xác dự báo

export interface ModelPerformanceSummary {
  model: string;
  sample_count: number;
  avg_mae: number | null;
  avg_rmse: number | null;
  avg_mape: number | null;
  min_mae: number | null;
  min_rmse: number | null;
}

export interface AccuracyTimeSeriesPoint {
  date: string;
  disease_type: string;
  model: string;
  predicted_cases: number;
  confidence_lower: number | null;
  confidence_upper: number | null;
  mae: number | null;
  rmse: number | null;
  mape: number | null;
}

export interface ForecastAccuracyReport {
  report_type: 'forecast-accuracy';
  period: { start_date: string; end_date: string };
  filters: { disease_type: string | null; model_used: string | null };
  summary: {
    total_forecasts: number;
    models_evaluated: number;
    best_model_by_mape: string | null;
  };
  model_performance: ModelPerformanceSummary[];
  time_series: AccuracyTimeSeriesPoint[];
  generated_at: string;
}

// Yêu cầu xuất báo cáo

// Khớp SUPPORTED_TYPES của POST /reports/export
export type ReportType =
  | 'epidemic'
  | 'forecast'
  | 'inventory'
  | 'shortage'
  | 'forecast-accuracy'
  | 'dashboard-summary';

export interface ExportReportRequest {
  report_type: ReportType;
  format?: 'pdf' | 'excel';
  start_date?: string;
  end_date?: string;
  location?: string;
  category?: string;
  disease_type?: string;
  model_used?: string;
}

// Dòng hiệu năng theo tháng (PerformanceTable)

