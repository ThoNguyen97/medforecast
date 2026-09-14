/**
 * Hợp đồng dữ liệu — /api/v1/dashboard/v2/alerts · /api/v1/dss/params · /api/v1/dss/norms
 * ---------------------------------------------------------------------------
 * 12/09/2026 — một công thức, một bộ tham số. Nguồn sự thật:
 *   backend/app/services/dss_dashboard.py (alerts_payload)
 *   backend/app/api/v1/dss_config.py
 *   backend/app/services/dss_demand.py (norms_payload)
 */
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
    so_ma?: number;
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
  overstock_factor: number;
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

export interface NormRoCell {
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
  /** Σ_ro p̂ · Norm — lượng cần cho MỘT ca dự báo của nhóm */
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
