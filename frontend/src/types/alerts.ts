export type AlertSeverity = 'critical' | 'high' | 'medium';

export interface Alert {
  id: number;
  supply_id: number;
  supply_name: string;
  alert_type: string;
  severity: AlertSeverity;
  current_stock: number | null;
  required_stock: number | null;
  shortage_date: string | null;
  message: string | null;
  is_resolved: boolean;
  created_at: string;
}

export interface AlertFilters {
  severity?: AlertSeverity | 'all';
  is_resolved?: boolean;
  dateRange?: string; // number of days as string, e.g. '7', '30', 'all'
}

export const ALERT_SEVERITY_LABELS: Record<AlertSeverity, string> = {
  critical: 'Nghiêm trọng',
  high: 'Cao',
  medium: 'Trung bình',
};

export const ALERT_SEVERITY_COLORS: Record<AlertSeverity, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'yellow',
};

export const ALERT_TYPE_LABELS: Record<string, string> = {
  low_stock: 'Tồn kho thấp',
  shortage: 'Thiếu hụt vật tư',
  critical_shortage: 'Thiếu hụt nghiêm trọng',
  expiring: 'Sắp hết hạn',
};
