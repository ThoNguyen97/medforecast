/**
 * Hợp đồng dữ liệu — GET /api/v1/dashboard/v2 và /v2/forecast
 * ---------------------------------------------------------------------------
 * MedForecast · phạm vi DSS thuần (Tuần 3, 11/09/2026)
 * Nguồn sự thật: backend/app/services/dss_dashboard.py
 *
 * Không có trường nào thuộc phân hệ mua sắm. "Thiếu hụt dự kiến" là
 * delta_need = max(0, d_forecast − s_usable), tính trên horizon_days.
 */

/** 'YYYY-MM' */
export type Period = string;

export type BlockCode = 'J00-J06' | 'J09-J18' | 'J20-J22';

/** Rổ phân cấp chăm sóc (NGT tách khỏi NT3 — Đ5). */
export type CareBucket = 'NGT' | 'NT1' | 'NT2' | 'NT3' | 'NT0';

/**
 * Bốn mức theo DOI. `grey` = KHÔNG đo được, tuyệt đối không hiển thị như xanh.
 */
export type AlertLevel = 'red' | 'amber' | 'green' | 'grey';

export type GreyReason = 'no_norm' | 'no_forecast' | 'no_stock_data' | 'period_not_closed';

export interface Thresholds {
  red_days: number;
  amber_days: number;
}

// ─── /v2 ─────────────────────────────────────────────────────────────────────

export interface DashboardMeta {
  generated_at: string;
  last_closed_period: Period | null;
  prev_closed_period: Period | null;
  open_period: Period | null;
  forecast_period: Period | null;
  focus: boolean;
  level: AlertLevel | null;
  limit: number;
  thresholds: Thresholds;
  horizon_days: number;
  fefo_window_days: number;
  assumptions_note: string;
}

export interface BlockCases {
  block_code: BlockCode;
  block_name: string;
  cases_last_closed: number;
  cases_prev: number;
  trend_pct: number | null;
}

export interface CasesSection {
  last_closed: {
    period: Period | null;
    cases: number;
    trend_pct: number;
    prev_period: Period | null;
    prev_cases: number;
  };
  open: { period: Period | null; cases: number; note: string };
  by_block: BlockCases[];
}

export interface ForecastTotal {
  point: number | null;
  lower: number | null;
  upper: number | null;
}

export interface ForecastBlockBrief {
  block: BlockCode;
  point: number;
  lower: number | null;
  upper: number | null;
}

export interface ForecastSummary {
  ready: boolean;
  target_period: Period | null;
  total: ForecastTotal;
  level: number;
  blocks: ForecastBlockBrief[];
  computed_at: string | null;
  ghi_chu: string[];
}

export interface DemandMeta {
  ready: boolean;
  so_ma?: number;
  horizon_days?: number;
  nguon_dinh_muc?: Record<string, string>;
  nhom_thieu_p_hat?: string[];
  nhom_thieu_dinh_muc?: string[];
  error?: string;
}

export interface LevelCounts {
  red: number;
  amber: number;
  green: number;
  grey: number;
  total: number;
  measured: number;
  zero_stock: number;
  fefo_codes?: number;
  ly_do_xam?: Partial<Record<GreyReason, number>>;
  san_sang: boolean;
}

export interface OverallRisk {
  level: 'Thấp' | 'Trung bình' | 'Cao';
  basis: string;
  is_provisional: boolean;
}

export interface RiskSection {
  selected: string;
  counts: LevelCounts & { nguong: Thresholds };
  focus: LevelCounts;
  all: LevelCounts;
  overall: OverallRisk;
  basis: string;
  canh_bao: string[];
}

export interface AlertRow {
  supply_code: string;
  ten: string;
  don_vi: string | null;
  nhom: string | null;
  danh_muc: string;
  s_total: number;
  s_usable: number;
  s_expiring: number;
  d_daily: number;
  d_forecast: number | null;
  delta_need: number | null;
  doi: number | null;
  muc: AlertLevel;
  ly_do_xam: GreyReason | null;
  fefo_ap_dung: boolean;
  ty_trong_hohap: number | null;
}

export interface DoiCategory {
  category: string;
  n: number;
  n_measured: number;
  median_doi: number | null;
  red: number;
  amber: number;
  green: number;
  grey: number;
}

export interface TrendPoint {
  period: Period;
  month?: string;
  cases: number | null;
  is_complete?: boolean;
}

export interface TrendSection {
  periods: Period[];
  total: TrendPoint[];
  by_block: Record<BlockCode, TrendPoint[]>;
  last_year: {
    total: TrendPoint[];
    by_block: Record<BlockCode, TrendPoint[]>;
  };
}

export interface CareLevelShare {
  block_code: BlockCode;
  ro: CareBucket;
  share_pct: number;
}

export interface CareLevelSection {
  shares: CareLevelShare[];
  cua_so: { tu_ky?: Period; den_ky?: Period; so_ky?: number };
  anh_xa_ro_do_nang: Record<string, string>;
  chan_doan_dinh_muc: Record<string, unknown>;
  ghi_chu: string;
}

export interface QualityBlock {
  block: BlockCode;
  rel_mae_codes?: number | null;
  mae_codes?: number | null;
  mpe_codes_pct?: number | null;
  n_codes?: number;
  n_steps?: number;
  rel_mae_group?: number | null;
  mpe_group_pct?: number | null;
  coverage_pct?: number | null;
  coverage_n?: number;
  weather?: boolean;
}

export interface QualitySection {
  available: boolean;
  source: string;
  phuong_an: string;
  run_at?: string | null;
  co_statsmodels?: boolean | null;
  rel_mae_codes?: number | null;
  rel_mae_codes_pooled?: number | null;
  improvement_vs_naive_pct?: number | null;
  coverage_mean_pct?: number | null;
  coverage_target_pct?: number;
  by_block?: QualityBlock[];
  ghi_chu?: string;
  canh_bao?: string;
}

export interface DssTableStatus {
  rows: number;
  latest: string | null;
}

export interface DataStatusSection {
  dss_tables: Record<string, DssTableStatus | null>;
  last_sync: {
    source: string;
    last_period: Period | null;
    rows_ingested: number;
    status: string;
    run_at: string;
  } | null;
  fefo: { codes: number; total: number };
  nguon_ton_kho: string | null;
}

export interface Insight {
  tone: 'info' | 'warn' | 'critical' | 'muted';
  text: string;
}

export interface DashboardV2 {
  meta: DashboardMeta;
  cases: CasesSection;
  forecast: ForecastSummary;
  demand: DemandMeta;
  risk: RiskSection;
  catalogue: { total: number; active: number; focus: number };
  alerts: AlertRow[];
  alerts_total_matched: number;
  doi_by_category: DoiCategory[];
  trend: TrendSection;
  care_level: CareLevelSection;
  quality: QualitySection;
  data_status: DataStatusSection;
  insights: Insight[];
}

export interface DashboardV2Params {
  focus: boolean;
  level: AlertLevel | null;
  limit?: number;
}

// ─── /v2/forecast ────────────────────────────────────────────────────────────

export interface ForecastBlockFull {
  block: BlockCode;
  block_name: string;
  region: string;
  anchor_period: Period;
  target_period: Period;
  point: number;
  lower: number | null;
  upper: number | null;
  level: number;
  n_resid: number;
  interval_reason: string | null;
  n_history_months: number;
  weather_used: boolean;
  model: {
    members: string[];
    members_used: string[];
    members_failed: Record<string, string>;
    config: Record<string, unknown>;
  };
  computed_at?: string;
  from_cache?: boolean;
}

export interface DashboardForecast {
  ready: boolean;
  blocks: ForecastBlockFull[];
  missing: string[];
  errors: string[];
  total: ForecastTotal;
  target_period: Period | null;
  anchor_period: Period | null;
  level: number;
  config: Record<string, unknown>;
  computed_at: string | null;
  ghi_chu: string[];
}

export const BLOCK_LABELS: Record<BlockCode, string> = {
  'J00-J06': 'Hô hấp trên',
  'J09-J18': 'Cúm & viêm phổi',
  'J20-J22': 'Hô hấp dưới khác',
};

export const LEVEL_LABELS: Record<AlertLevel, string> = {
  red: 'Đỏ',
  amber: 'Vàng',
  green: 'Xanh',
  grey: 'Xám',
};

export const GREY_REASON_LABELS: Record<GreyReason, string> = {
  no_norm: 'Không có định mức',
  no_forecast: 'Không có dự báo',
  no_stock_data: 'Không có dữ liệu tồn',
  period_not_closed: 'Kỳ chưa chốt',
};

export const CARE_BUCKET_LABELS: Record<CareBucket, string> = {
  NGT: 'Ngoại trú',
  NT1: 'Nội trú cấp 1',
  NT2: 'Nội trú cấp 2',
  NT3: 'Nội trú cấp 3',
  NT0: 'Nội trú chưa phân cấp',
};
