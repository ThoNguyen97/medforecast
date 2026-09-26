
export interface SystemConfig {
  id: number;
  config_key: string;
  config_value: string;
  description: string | null;
  updated_by: number | null;
  updated_at: string;
}

export interface ConfigUpdateRequest {
  config_value: string;
}

// Nhật ký thay đổi cấu hình
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

