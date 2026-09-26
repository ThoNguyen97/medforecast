/** Hợp đồng dữ liệu /dashboard/v2/alerts, /dss/params, /dss/norms
 *  (backend: dss_dashboard.py, dss_config.py, dss_demand.py). */
import type { AlertLevel, AlertRow, BlockCode, CareBucket, Period, Thresholds } from './dashboardV2';

// ─── /dashboard/v2/alerts ────────────────────────────────────────────────────

export interface AlertsQuery {
  focus: boolean;
  level: AlertLevel | null;
  q?: string;
  danh_muc?: string;
  limit?: number;
  offset?: number;
}

export interface AlertsCounts {
  red: number;
  amber: number;
  green: number;
  grey: number;
  total: number;
  measured: number;
  zero_stock: number;
  /** số mã DOI dùng mẫu số dự báo / lùi về tiêu hao 12 kỳ */
  fefo_codes?: number;
  stock_source?: string | null; // 'fact_inventory_lot@YYYY-MM-DD' | 'inventory' | 'khong_co'
  ly_do_xam?: Record<string, number>;
  san_sang: boolean;
}

export interface AlertsPayload {
  meta: {
    generated_at: string;
    last_closed_period: Period | null;
    forecast_period: Period | null;
    focus: boolean;
    level: AlertLevel | null;
    q: string;
    danh_muc: string;
    limit: number;
    offset: number;
    thresholds: Thresholds;
    horizon_days: number;
    fefo_window_days: number;
    assumptions_note: string;
  };
  forecast: {
    ready: boolean;
    target_period: Period | null;
    total: { point: number | null; lower: number | null; upper: number | null };
    computed_at: string | null;
    blocks: { block: BlockCode; point: number }[];
  };
  demand: {
    ready: boolean;
    /** số mã có nhu cầu dự báo trong phạm vi đang xem */
    so_ma?: number;
    so_ma_toan_danh_muc?: number;
    horizon_days?: number;
    nguon_dinh_muc?: Record<string, string>;
    error?: string;
  };
  counts: AlertsCounts;
  basis: string;
  canh_bao: string[];
  danh_muc: string[];
  total: number;
  rows: AlertRow[];
}

// ─── /dss/params ─────────────────────────────────────────────────────────────

export interface ParamMeta {
  ten: string;
  y_nghia: string;
  min?: number;
  max?: number;
  kieu?: 'ky';
}

export interface ParamGroup<T extends Record<string, number | string>> {
  gia_tri: T;
  mac_dinh: T;
  mo_ta: Record<keyof T & string, ParamMeta>;
  nguon: string | null;
  config_key: string;
}

export interface ThresholdParams extends Record<string, number | string> {
  doi_red_days: number;
  doi_amber_days: number;
  horizon_days: number;
  fefo_window_days: number;
}

export interface CareLevelParams extends Record<string, number | string> {
  window_periods: number;
  min_period: string;
  min_cases_per_bucket: number;
  shrink_k0: number;
}

export interface DssParams {
  thresholds: ParamGroup<ThresholdParams>;
  care_level: ParamGroup<CareLevelParams>;
  cong_thuc: string[];
  da_doi?: { thresholds?: Partial<ThresholdParams>; care_level?: Partial<CareLevelParams> };
}

export interface DssParamsUpdate {
  thresholds?: Partial<ThresholdParams>;
  care_level?: Partial<CareLevelParams>;
}

// ─── /dss/norms ──────────────────────────────────────────────────────────────

interface NormRoCell {
  tieu_hao: number;
  ca: number;
  norm: number;
  gop: boolean;
  p_hat: number;
}

export interface NormRow {
  supply_code: string;
  ten: string;
  don_vi: string | null;
  nhom: string | null;
  tieu_hao_tong: number;
  norm_gop: number;
  /** Σ_ro p̂ · Norm: lượng cần cho một ca dự báo */
  norm_hieu_dung: number;
  theo_ro: Partial<Record<CareBucket, NormRoCell>>;
}

export interface NormsPayload {
  block: BlockCode;
  periods: Period[];
  cfg: CareLevelParams;
  ro: { ro: CareBucket; ten: string; ca: number; p_hat: number; mau_nho: boolean }[];
  total: number;
  offset: number;
  limit: number;
  rows: NormRow[];
  cong_thuc: string;
}
