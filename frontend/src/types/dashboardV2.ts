/**
 * Hợp đồng dữ liệu — GET /api/v1/dashboard/v2
 * ---------------------------------------------------------------------------
 * MedForecast AI · phạm vi DSS (đã bỏ phân hệ mua sắm)
 * Đặt tại: frontend/src/types/dashboardV2.ts
 *
 * Một lần gọi dựng đủ màn hình. Tham số truy vấn:
 *   ?period=2026-10&block=all&watchlist_limit=25
 *
 * BẢY TRƯỜNG BỊ LOẠI BỎ — không được xuất hiện ở bất kỳ endpoint nào:
 *   suggested_qty · suggested_import · order_by_date · expected_delivery_date
 *   capacity_constrained · moq · safety_stock · required_stock
 *   estimated_cost · status(pending|approved|ordered) · total_inventory_value
 */

// ─── Nguyên thuỷ ─────────────────────────────────────────────────────────────

/** 'YYYY-MM' */
export type Period = string;
/** 'YYYY-MM-DD' */
export type IsoDate = string;
/** ISO 8601 có múi giờ */
export type IsoDateTime = string;

export type BlockCode = 'J00-J06' | 'J09-J18' | 'J20-J22';

/** Năm rổ tính định mức. Đ5 buộc tách NGT khỏi NT3 (chênh 3,5 lần). */
export type CareBucket = 'NGT' | 'NT1' | 'NT2' | 'NT3' | 'NT0';

/**
 * Bốn mức cảnh báo theo DOI.
 * QUAN TRỌNG: d = 0 (không định mức / dự báo = 0) → 'grey', TUYỆT ĐỐI không
 * phải 'green'. Nếu để rơi vào 'green' thì 3.888 mã không có định mức sẽ
 * hiện màu xanh và dashboard trông đẹp mà vô nghĩa.
 */
export type AlertLevel = 'red' | 'amber' | 'green' | 'grey';

export type GreyReason = 'no_norm' | 'no_forecast' | 'no_stock_data' | 'period_not_closed';

export type ConfidenceGrade = 'tot' | 'kha' | 'yeu' | 'chua_du_du_lieu';

export type CheckStatus = 'ok' | 'warn' | 'fail';

// ─── meta ────────────────────────────────────────────────────────────────────

export interface DataFreshness {
  /** Kỳ đã chốt gần nhất (is_complete = 1). MỌI KPI neo vào đây, không neo
   *  vào max(recorded_at) — kỳ đang mở làm xu hướng nhảy 6500%. */
  last_closed_period: Period;
  /** Kỳ đang mở. Hiển thị riêng với nhãn "chưa chốt", không tính xu hướng. */
  open_period: Period | null;
  last_sync_at: IsoDateTime | null;
  sync_status: 'ok' | 'stale' | 'failed';
  stale_days: number;
}

/** Mọi giả định lộ ra ngoài. Không hằng số ẩn trong mã. */
export interface Assumptions {
  /** Chân trời cảnh báo, ngày. Cũng là mẫu số của d_daily. */
  horizon_days: number;
  /** Cửa sổ FEFO. Bằng horizon_days theo mặc định — không còn khái niệm
   *  chu kỳ rà soát T sau khi bỏ đặt hàng. */
  fefo_window_days: number;
  /** Hằng số cấu hình toàn hệ thống, KHÔNG phải cột theo từng mã. */
  standard_lead_time_days: number;
  doi_red_days: number;
  doi_amber_days: number;
  /** Luôn false trong phạm vi này. Giao diện PHẢI hiển thị câu
   *  "chưa trừ hàng đang về" khi trường này false. */
  incoming_stock_considered: boolean;
}

export interface DashboardMeta {
  period: Period;
  period_label: string;
  generated_at: IsoDateTime;
  data_as_of: DataFreshness;
  assumptions: Assumptions;
}

// ─── Tầng 1 · dịch tễ ────────────────────────────────────────────────────────

export interface EnsembleMemberWeight {
  member: string;          // 'sarimax' | 'xgboost' | 'prophet' | 'seasonal_naive' | ...
  weight: number;          // 0..1, tổng = 1
}

/** Không có khối này thì DOI là ý kiến, không phải kết luận. Nguồn: bảng
 *  forecast_accuracy do khung backtest rolling-origin sinh ra (P3). */
export interface ForecastAccuracy {
  mape_last3: number | null;
  mae_last3: number | null;
  n_backtest: number;
  grade: ConfidenceGrade;
}

export interface ForecastPoint {
  point: number;
  /** Khoảng tin cậy 80%. hi80 là đầu vào của doi_days_worst. */
  lo80: number | null;
  hi80: number | null;
}

export interface BlockEpidemiology {
  block_code: BlockCode;
  block_name: string;
  cases_last_closed: number;
  cases_prev: number;
  trend_pct: number;
  forecast: ForecastPoint;
  forecast_trend_pct: number;
  model_mix: EnsembleMemberWeight[];
  accuracy: ForecastAccuracy;
}

export interface EpidemiologySection {
  blocks: BlockEpidemiology[];
  total_cases_last_closed: number;
  total_forecast: number;
}

// ─── Tầng 2 · cơ cấu phân cấp chăm sóc ───────────────────────────────────────

export interface CareBucketShare {
  ro: CareBucket;
  cases: number;
  /** 0..1 */
  share: number;
}

export interface BlockCareLevelMix {
  block_code: BlockCode;
  buckets: CareBucketShare[];
}

/** Bằng chứng bảo vệ mạnh nhất của đề tài: số đo thật so với hằng số gõ tay.
 *  Đ4 đo 42,2/40,8/17,0 trong khi severity_rates ghi 71,49/23,51/5. */
export interface CareLevelComparison {
  block_code: BlockCode;
  level: '1' | '2' | '3';
  observed_pct: number;
  configured_pct: number | null;
  delta_pp: number | null;
}

export interface CareLevelMixSection {
  /** 'observed' = suy từ dữ liệu; 'configured' = đang dùng lớp ghi đè tay. */
  source: 'observed' | 'configured';
  /** 'YYYY-MM..YYYY-MM' */
  window: string;
  by_block: BlockCareLevelMix[];
  vs_configured: CareLevelComparison[];
}

// ─── Tầng 3 · tín hiệu tồn kho ───────────────────────────────────────────────

export interface LevelBucket {
  count: number;
  /** Chỉ có ở red/amber. Giá trị đang có nguy cơ, KHÔNG phải chi phí sẽ chi. */
  value_at_risk?: number;
}

export interface GreyBucket extends LevelBucket {
  /** Chia nhỏ lý do. Không có nó thì 3.888 mã thành một khối im lặng. */
  reasons: Partial<Record<GreyReason, number>>;
}

export interface InventorySignalSection {
  items_total: number;
  items_with_norm: number;
  coverage_pct: number;
  levels: {
    red: LevelBucket;
    amber: LevelBucket;
    green: LevelBucket;
    grey: GreyBucket;
  };
}

// ─── Danh sách theo dõi ──────────────────────────────────────────────────────

/** Truy ngược cảnh báo về nguyên nhân dịch tễ — lý do tồn tại của đề tài.
 *  '__baseline__' là phần nhu cầu nền không gán được cho nhóm bệnh nào. */
export interface DemandDriver {
  block_code: BlockCode | '__baseline__';
  contribution_pct: number;
}

export interface NearestExpiry {
  lot_code: string | null;
  expiry_date: IsoDate;
  quantity: number;
  days_left: number;
}

export interface WatchlistConfidence {
  grade: ConfidenceGrade;
  mape: number | null;
  /** Nhóm bệnh đóng góp lớn nhất — cơ sở của sai số. */
  basis: BlockCode | null;
  xyz: 'X' | 'Y' | 'Z' | null;
}

export interface WatchlistItem {
  supply_code: string;
  supply_name: string;
  unit: string | null;
  category: string | null;

  /** Giữ lại từ ABC-XYZ của Phase 0, nhưng ĐỔI VAI: không còn quyết định đặt
   *  hàng, mà để xếp thứ tự cảnh báo. Nhóm A × Z nguy hiểm nhất. */
  abc_class: 'A' | 'B' | 'C' | null;
  xyz_class: 'X' | 'Y' | 'Z' | null;
  is_vital: boolean;

  stock_raw: number;
  /** FEFO theo công thức clamp: u_b = clamp(D(e_b) − C_(b−1), 0, q_b).
   *  Đây là SỐ CHÍNH. */
  stock_usable: number;
  /** Loại thẳng mọi lô hết hạn trong cửa sổ. Bi quan hơn FEFO thật; chỉ dùng
   *  hiển thị trong phần giải thích. Chênh lệch với stock_usable chính là
   *  "lượng cứu được nếu dùng đúng thứ tự hạn dùng". */
  stock_usable_conservative: number;
  blocked_by_expiry: number;

  d_forecast_30d: number;
  d_baseline_30d: number;
  d_total_30d: number;
  d_daily: number;

  /** stock_usable / d_daily. null khi d_daily = 0 → level = 'grey'. */
  doi_days: number | null;
  /** Tính trên hi80 của dự báo. Chênh với doi_days = rủi ro mùa vụ — chỗ mô
   *  hình dịch tễ chứng minh giá trị. */
  doi_days_worst: number | null;

  level: AlertLevel;
  /** Bắt buộc khác null khi level = 'grey'. */
  level_reason: GreyReason | null;
  /** f(level, abc_class, is_vital). Nhỏ hơn = khẩn hơn. */
  priority: number;

  /** max(0, d_total_30d − stock_usable). Lượng thiếu hụt lâm sàng cần chuẩn
   *  bị — KHÔNG phải lượng đặt hàng, không làm tròn MOQ, không áp trần kho. */
  delta_need: number;

  confidence: WatchlistConfidence;
  drivers: DemandDriver[];
  nearest_expiry: NearestExpiry | null;

  /** Một câu tiếng Việt. Cảnh báo không có lý do sẽ bị bỏ qua. Bắt buộc
   *  khác rỗng với mọi level ngoài 'green'. */
  explain: string;
}

// ─── Hạn dùng ────────────────────────────────────────────────────────────────

export interface ExpiryBucket {
  label: string;           // 'đã quá hạn' | '≤ 30 ngày' | '31–90 ngày' | '> 90 ngày'
  lots: number;
  qty: number;
  value: number | null;
}

export interface ExpiryTopLot {
  supply_code: string;
  supply_name: string;
  lot_code: string | null;
  expiry_date: IsoDate;
  quantity: number;
  value: number | null;
  /** Phần lô này còn kịp tiêu thụ trước hạn theo nhu cầu dự báo. Chênh với
   *  quantity là lượng gần như chắc chắn phải huỷ. */
  consumable_before_expiry: number;
}

export interface ExpiryRiskSection {
  window_days: number;
  buckets: ExpiryBucket[];
  top_lots: ExpiryTopLot[];
  /** Độ phủ hạn dùng quyết định FEFO áp được cho bao nhiêu phần kho.
   *  Dưới 50% thì màn hình phải ghi rõ phạm vi áp dụng. */
  coverage: { lots_with_expiry: number; lots_total: number; pct: number };
}

// ─── Chất lượng dữ liệu ──────────────────────────────────────────────────────

export interface QualityCheck {
  id:
    | 'period_closed'
    | 'norm_coverage'
    | 'expiry_coverage'
    | 'forecast_freshness'
    | 'care_level_missing';
  label: string;
  status: CheckStatus;
  detail: string;
}

export interface DataQualitySection {
  checks: QualityCheck[];
}

// ─── Gói trả về ──────────────────────────────────────────────────────────────

export interface DashboardV2 {
  meta: DashboardMeta;
  epidemiology: EpidemiologySection;
  care_level_mix: CareLevelMixSection;
  inventory_signal: InventorySignalSection;
  watchlist: WatchlistItem[];
  expiry_risk: ExpiryRiskSection;
  data_quality: DataQualitySection;
}

// ─── Hằng số hiển thị ────────────────────────────────────────────────────────

export const LEVEL_LABEL: Record<AlertLevel, string> = {
  red: 'Nguy cơ thiếu hụt',
  amber: 'Cần theo dõi sát',
  green: 'Tồn kho an toàn',
  grey: 'Chưa đủ thông tin',
};

export const GREY_REASON_LABEL: Record<GreyReason, string> = {
  no_norm: 'Chưa có định mức tiêu hao',
  no_forecast: 'Chưa có dự báo cho kỳ này',
  no_stock_data: 'Không có dữ liệu tồn kho',
  period_not_closed: 'Kỳ dữ liệu chưa chốt',
};

export const BUCKET_LABEL: Record<CareBucket, string> = {
  NGT: 'Ngoại trú',
  NT1: 'Nội trú · cấp 1 (nặng)',
  NT2: 'Nội trú · cấp 2 (vừa)',
  NT3: 'Nội trú · cấp 3 (nhẹ)',
  NT0: 'Nội trú · chưa phân cấp',
};

export const CONFIDENCE_LABEL: Record<ConfidenceGrade, string> = {
  tot: 'Tốt',
  kha: 'Khá',
  yeu: 'Yếu',
  chua_du_du_lieu: 'Chưa đủ dữ liệu',
};

/**
 * Quy tắc phân mức. Đặt ở một chỗ duy nhất để backend và frontend không lệch.
 * Backend là nơi TÍNH; hàm này chỉ để kiểm tra lại ở tầng hiển thị.
 */
export function classifyDoi(
  doiDays: number | null,
  a: Pick<Assumptions, 'doi_red_days' | 'doi_amber_days'>,
): AlertLevel {
  if (doiDays === null || !Number.isFinite(doiDays)) return 'grey';
  if (doiDays <= a.doi_red_days) return 'red';
  if (doiDays <= a.doi_amber_days) return 'amber';
  return 'green';
}
