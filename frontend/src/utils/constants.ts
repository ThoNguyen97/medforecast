// Đường dẫn tương đối: dev qua Vite proxy, production qua nginx, tránh CORS
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const TOKEN_KEY = 'medforecast_token';
export const REFRESH_TOKEN_KEY = 'medforecast_refresh_token';
export const USER_KEY = 'medforecast_user';
export const TOKEN_EXPIRY_KEY = 'medforecast_token_expiry';

export const DASHBOARD_REFRESH_INTERVAL_MS = 5 * 60 * 1000;

// 8 nhãn danh mục thuốc đồng bộ nguyên văn từ HIS (khoá = nhãn); medicine/other cho
// dữ liệu nhập tay
export const SUPPLY_CATEGORY_LABELS: Record<string, string> = {
  'Kháng sinh': 'Kháng sinh',
  'Thuốc hạ sốt giảm đau': 'Thuốc hạ sốt giảm đau',
  'Thuốc long đờm': 'Thuốc long đờm',
  'Thuốc giãn phế quản': 'Thuốc giãn phế quản',
  'Corticoid': 'Corticoid',
  'Kháng histamin': 'Kháng histamin',
  'Dịch truyền': 'Dịch truyền',
  'Khác': 'Khác',
  medicine: 'Thuốc',
  other: 'Khác',
};

export const USER_ROLE_LABELS: Record<string, string> = {
  Administrator: 'Quản trị viên',
  Pharmacist: 'Dược sĩ',
  Inventory_Manager: 'Quản lý kho',
};

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
} as const;

export const APP_NAME = 'MedForecast AI';
export const APP_DESCRIPTION = 'Hệ thống Dự báo Nhu cầu Thuốc';
