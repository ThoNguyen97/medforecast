// System Configuration Types

export interface SystemConfig {
  id: number;
  config_key: string;
  config_value: string;
  description: string | null;
  updated_by: number | null;
  updated_at: string;
}

export interface ConversionRatio {
  id: number;
  disease_type: string;
  supply_id: number;
  supply_name?: string;
  ratio: number;
  unit: string | null;
  updated_by: number | null;
  updated_at: string;
}

export interface ShortageThreshold {
  /** Global threshold (per-supply chưa được hỗ trợ ở backend) */
  critical_days: number;
  high_days: number;
  medium_days: number;
}

export interface ConfigUpdateRequest {
  config_value: string;
}

export interface ConversionRatiosUpdateRequest {
  ratios: Array<{
    disease_type: string;
    supply_id: number;
    ratio: number;
    unit?: string;
  }>;
}

export interface ThresholdsUpdateRequest {
  critical_days: number;
  high_days: number;
  medium_days: number;
}

// Audit log type (for change history)
export interface AuditLog {
  id: number;
  user_id: number | null;
  username?: string;
  action: string;
  table_name: string | null;
  record_id: number | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogsResponse {
  items: AuditLog[];
  total: number;
  skip: number;
  limit: number;
}

// Grouped config sections (convenience types for the Settings UI)
export type ConfigSection = 'thresholds' | 'conversion-ratios' | 'unit-prices' | 'history';

export const CONFIG_SECTION_LABELS: Record<ConfigSection, string> = {
  thresholds: 'Ngưỡng cảnh báo thiếu hụt',
  'conversion-ratios': 'Tỷ lệ quy đổi',
  'unit-prices': 'Đơn giá vật tư',
  history: 'Lịch sử thay đổi',
};

// Phạm vi đồ án là ba KHỐI ICD-10 hô hấp — khớp app/utils/icd_groups.py phía
// backend. Danh sách cũ (sốt xuất huyết / cúm mùa) đã ngoài phạm vi: để lại sẽ
// cho người dùng chọn một mã mà mọi truy vấn phía sau không có dữ liệu.
export const DISEASE_TYPE_OPTIONS = [
  { value: 'J00-J06', label: 'Nhiễm khuẩn hô hấp trên (J00-J06)' },
  { value: 'J09-J18', label: 'Viêm phổi, cúm (J09-J18)' },
  { value: 'J20-J22', label: 'Nhiễm khuẩn hô hấp dưới cấp (J20-J22)' },
] as const;
