// API Configuration
// Đường dẫn tương đối: dev đi qua Vite proxy, production đi qua nginx (location /api/) —
// không phụ thuộc host, tránh lỗi CORS/Network Error khi deploy.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// Auth
export const TOKEN_KEY = 'medforecast_token';
export const REFRESH_TOKEN_KEY = 'medforecast_refresh_token';
export const USER_KEY = 'medforecast_user';
export const TOKEN_EXPIRY_KEY = 'medforecast_token_expiry';

// Session
export const SESSION_TIMEOUT_MINUTES = 30;

// Pagination
export const DEFAULT_PAGE_SIZE = 20;
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

// Dashboard
export const DASHBOARD_REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

// Disease types — 4 bệnh hô hấp dùng để dự báo nhu cầu kho
export const DISEASE_TYPE_LABELS: Record<string, string> = {
  J20: 'Viêm phế quản cấp',
  J06: 'Nhiễm trùng đường hô hấp trên cấp',
  J02: 'Viêm họng cấp',
  J01: 'Viêm xoang cấp',
  // Giữ lại nhãn 'respiratory' để tương thích với dữ liệu hiện có
  respiratory: 'Bệnh hô hấp',
};

// Supply categories
export const SUPPLY_CATEGORY_LABELS: Record<string, string> = {
  mask: 'Khẩu trang',
  glove: 'Găng tay',
  test_kit: 'Kit xét nghiệm',
  disinfectant: 'Dung dịch sát khuẩn',
  medicine: 'Thuốc',
  iv_fluid: 'Dịch truyền',
  other: 'Khác',
};

// Alert severity
export const ALERT_SEVERITY_LABELS: Record<string, string> = {
  critical: 'Nghiêm trọng',
  high: 'Cao',
  medium: 'Trung bình',
  low: 'Thấp',
};

export const ALERT_SEVERITY_COLORS: Record<string, string> = {
  critical: 'danger',
  high: 'warning',
  medium: 'yellow',
  low: 'neutral',
};

// Stock status
export const STOCK_STATUS_LABELS: Record<string, string> = {
  safe: 'An toàn',
  low: 'Thấp',
  critical: 'Nguy hiểm',
};

// User roles
export const USER_ROLE_LABELS: Record<string, string> = {
  Administrator: 'Quản trị viên',
  Pharmacist: 'Dược sĩ',
  Inventory_Manager: 'Quản lý kho',
};

// Forecast periods
export const FORECAST_PERIOD_OPTIONS = [
  { value: 7, label: '7 ngày' },
  { value: 14, label: '14 ngày' },
  { value: 30, label: '30 ngày' },
];

// Navigation routes
export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  DASHBOARD: '/dashboard',
  INVENTORY: '/inventory',
  FORECASTING: '/forecasting',
  ALERTS: '/alerts',
  EPIDEMIOLOGY: '/epidemiology',
  WEATHER: '/weather',
  REPORTS: '/reports',
  SETTINGS: '/settings',
  SUPPLY_NORMS: '/supply-norms',
  SUPPLY_PLAN: '/supply-plan',
} as const;

// App info
export const APP_NAME = 'MedForecast AI';
export const APP_DESCRIPTION = 'Hệ thống Dự báo Nhu cầu Vật tư Y tế';
