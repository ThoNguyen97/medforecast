// ── Report filter types ───────────────────────────────────────────────────────

export interface ReportFilters {
  start_date?: string; // YYYY-MM-DD
  end_date?: string;   // YYYY-MM-DD
  location?: string;
  category?: string;
  disease_type?: string;
  model_used?: string;
}

// ── Consumption report ────────────────────────────────────────────────────────

export interface ConsumptionSupplyItem {
  supply_name: string;
  unit: string;
  total_required: number;
  active_days: number;
  avg_daily_consumption: number;
}

export interface ConsumptionCategory {
  category: string;
  total_required: number;
  supplies: ConsumptionSupplyItem[];
}

export interface ConsumptionReport {
  report_type: 'consumption';
  period: { start_date: string; end_date: string };
  filters: { location: string | null; category: string | null };
  summary: {
    total_required_across_all_categories: number;
    categories_count: number;
  };
  categories: ConsumptionCategory[];
  generated_at: string;
}

// ── Forecast accuracy report ──────────────────────────────────────────────────

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

// ── Inventory turnover report ─────────────────────────────────────────────────

export interface TurnoverItem {
  supply_id: number;
  supply_name: string;
  category: string;
  unit: string;
  location: string | null;
  current_stock: number;
  safety_stock: number;
  total_required_in_period: number;
  turnover_rate: number | null;
  days_of_supply: number | null;
  stock_value: number;
  stock_status: 'safe' | 'critical' | 'out_of_stock';
}

export interface InventoryTurnoverReport {
  report_type: 'inventory-turnover';
  period: { start_date: string; end_date: string; period_days: number };
  filters: { location: string | null; category: string | null };
  summary: {
    total_items: number;
    avg_turnover_rate: number;
    high_turnover_items: number;
    out_of_stock_items: number;
  };
  items: TurnoverItem[];
  generated_at: string;
}

// ── Export request ────────────────────────────────────────────────────────────

export type ReportType = 'consumption' | 'forecast-accuracy' | 'inventory-turnover';

export interface ExportReportRequest {
  report_type: ReportType;
  start_date?: string;
  end_date?: string;
  location?: string;
  category?: string;
  disease_type?: string;
  model_used?: string;
}

// ── Monthly performance row (PerformanceTable) ────────────────────────────────

export interface MonthlyPerformanceRow {
  month: string;          // e.g. "2025-01"
  month_label: string;    // e.g. "Tháng 1/2025"
  total_forecasts: number;
  avg_mae: number | null;
  avg_rmse: number | null;
  avg_mape: number | null;
  best_model: string | null;
}
